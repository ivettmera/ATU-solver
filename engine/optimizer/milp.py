"""
Optimizador de despacho — Programación Lineal Entera Mixta (MILP) con Google OR-Tools/CBC.

Recalcula el despacho óptimo cuando el gating lo dispara (anomalía de demanda o incidencia).
El modelo decide cuántos buses de cada servicio salen de cada terminal en el horizonte actual,
para minimizar la demanda no servida y el costo operativo bajo recursos finitos.

Modelo:
  Variables enteras:  n[s, term]  = nº de buses del servicio s despachados desde el terminal term.
  Variables continuas: unmet[s]   = demanda del servicio s que queda sin cubrir (≥ 0).

  Asignación de demanda: cada par OD se asigna al servicio más expreso que atiende ambos
  extremos (los pasajeros prefieren el servicio más rápido disponible); así D[s] particiona la
  demanda total sin doble conteo.

  Capacidad del servicio s:  cap[s] = (Σ_term n[s,term]) · capacidad_bus · factor_incidencia[s]
  donde factor_incidencia[s] ∈ [0,1] degrada la capacidad efectiva si hay estaciones de su ruta
  bloqueadas o con capacidad reducida.

  Restricciones duras:
    unmet[s] ≥ D[s] − cap[s]                         (la demanda no cubierta cuenta)
    Σ_{s,term} n[s,term] ≤ min(flota_total, conductores)   (recursos finitos)
    0 ≤ n[s,term] ≤ max_despachos                    (límite por headway en el horizonte)

  Objetivo:  min  W_UNMET · Σ_s unmet[s]  +  W_OPER · Σ_{s,term} n[s,term]
  (cubrir demanda pesa mucho más que el costo por bus, pero el costo evita sobre-despachar.)

Si el solver no está disponible o el modelo es infactible, se cae con elegancia al itinerario
base.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np
from ortools.linear_solver import pywraplp

from engine.network import topology
from engine.optimizer.dispatch_plan import Despacho, DispatchPlan

# Pesos del objetivo (pasajero no servido vs. bus despachado).
W_UNMET = 1.0
W_OPER = 12.0


@dataclass(frozen=True)
class RestriccionesFlota:
    """Recursos finitos y límites operativos que acotan el despacho."""

    flota_total: int
    conductores_disponibles: int
    capacidad_bus: int
    max_despachos: int = 20  # tope de buses por (servicio, terminal) en el horizonte


@dataclass(frozen=True)
class IncidenciaOperativa:
    """Incidencia que degrada la capacidad efectiva en una estación."""

    estacion: str
    bloqueado: bool = False
    capacidad_reducida_pct: float = 0.0  # 0..100

    def reduccion(self) -> float:
        """Fracción de capacidad perdida en [0,1] (bloqueo = pérdida total)."""
        if self.bloqueado:
            return 1.0
        return min(max(self.capacidad_reducida_pct, 0.0), 100.0) / 100.0


def asignar_demanda_a_servicios(m_hat: np.ndarray) -> dict[str, float]:
    """
    Reparte la demanda OD entre servicios sin doble conteo.

    Cada par (origen, destino) con demanda > 0 se asigna al servicio que atiende ambos extremos
    y tiene **menos paradas** (el más expreso); el Regular siempre es candidato de respaldo.
    """
    demanda = {s.codigo: 0.0 for s in topology.SERVICIOS}
    m = np.maximum(m_hat, 0.0)  # la demanda no puede ser negativa

    # Conjunto de paradas por servicio, ordenados de más expreso (menos paradas) a menos.
    servicios = sorted(topology.SERVICIOS, key=lambda s: len(s.paradas))
    paradas_idx = {s.codigo: set(s.indices_paradas()) for s in servicios}

    n = topology.N_ESTACIONES
    for o in range(n):
        for d in range(n):
            carga = m[o, d]
            if carga <= 0.0 or o == d:
                continue
            for s in servicios:
                idx = paradas_idx[s.codigo]
                if o in idx and d in idx:
                    demanda[s.codigo] += float(carga)
                    break
    return demanda


def factor_capacidad_por_servicio(
    incidencias: list[IncidenciaOperativa],
) -> dict[str, float]:
    """
    Factor de capacidad efectiva por servicio según las incidencias en su ruta.

    factor[s] = Π (1 − reducción_i) sobre las incidencias en estaciones que s atiende.
    """
    factor = {s.codigo: 1.0 for s in topology.SERVICIOS}
    if not incidencias:
        return factor

    for s in topology.SERVICIOS:
        f = 1.0
        for inc in incidencias:
            if s.atiende(inc.estacion):
                f *= (1.0 - inc.reduccion())
        factor[s.codigo] = f
    return factor


def itinerario_base(ahora: datetime, norma_delta: float = 0.0) -> DispatchPlan:
    """
    Itinerario histórico precalculado (caso normal del gating, costo de CPU cero).

    Un despacho regular desde cada terminal del corredor.
    """
    despachos = [
        Despacho(servicio="REG", terminal_salida=terminal, hora_salida=ahora, num_buses=2)
        for terminal in topology.TERMINALES
    ]
    return DispatchPlan(
        calculado_en=ahora,
        norma_delta=norma_delta,
        optimizado=False,
        despachos=despachos,
    )


def resolver_despacho(
    ahora: datetime,
    m_hat: np.ndarray,
    restricciones: RestriccionesFlota,
    norma_delta: float,
    incidencias: list[IncidenciaOperativa] | None = None,
) -> DispatchPlan:
    """
    Resuelve el despacho óptimo con MILP (OR-Tools/CBC) bajo las restricciones dadas.

    Devuelve el plan optimizado; si el solver no está disponible o el modelo es infactible,
    cae al itinerario base.
    """
    incidencias = incidencias or []
    demanda = asignar_demanda_a_servicios(m_hat)
    factor = factor_capacidad_por_servicio(incidencias)

    solver = pywraplp.Solver.CreateSolver("CBC")
    if solver is None:  # pragma: no cover - depende del entorno
        return itinerario_base(ahora, norma_delta)

    cap_bus = restricciones.capacidad_bus
    recursos = min(restricciones.flota_total, restricciones.conductores_disponibles)

    # Variables de despacho n[s, term] solo en terminales válidos de cada servicio.
    n: dict[tuple[str, str], pywraplp.Variable] = {}
    for s in topology.SERVICIOS:
        for term in topology.terminales_de_servicio(s):
            n[(s.codigo, term)] = solver.IntVar(0, restricciones.max_despachos, f"n_{s.codigo}_{term}")

    # Variables de demanda no servida y restricción de capacidad por servicio.
    unmet: dict[str, pywraplp.Variable] = {}
    for s in topology.SERVICIOS:
        unmet[s.codigo] = solver.NumVar(0, solver.infinity(), f"unmet_{s.codigo}")
        buses_s = [n[(s.codigo, term)] for term in topology.terminales_de_servicio(s)]
        cap_s = solver.Sum(buses_s) * cap_bus * factor[s.codigo]
        # unmet[s] >= D[s] - cap[s]
        solver.Add(unmet[s.codigo] >= demanda[s.codigo] - cap_s)

    # Recursos finitos: total de buses despachados ≤ min(flota, conductores).
    solver.Add(solver.Sum(list(n.values())) <= recursos)

    # Objetivo.
    solver.Minimize(
        W_UNMET * solver.Sum(list(unmet.values()))
        + W_OPER * solver.Sum(list(n.values()))
    )

    estado = solver.Solve()
    if estado not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        return itinerario_base(ahora, norma_delta)

    despachos = [
        Despacho(
            servicio=codigo,
            terminal_salida=term,
            hora_salida=ahora,
            num_buses=int(round(var.solution_value())),
        )
        for (codigo, term), var in n.items()
        if var.solution_value() >= 0.5
    ]

    return DispatchPlan(
        calculado_en=ahora,
        norma_delta=norma_delta,
        optimizado=True,
        despachos=despachos,
    )

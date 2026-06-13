"""
Optimizador de despacho — Programación Lineal Entera Mixta (MILP) con Google OR-Tools/CBC.

Recalcula el despacho óptimo sobre un horizonte deslizante cuando el gating lo dispara.

Formulación objetivo (a implementar en Fase 3):
  - Variables: nº de buses despachados por (servicio, terminal, bloque).
  - Objetivo: minimizar demanda no servida + costo operativo (buses despachados).
  - Restricciones duras:
      * flota total finita por terminal (extremos + Central),
      * conductores disponibles,
      * capacidad por bus,
      * headway mínimo entre salidas,
      * cobertura de la demanda estimada M̂(t).
  - Las incidencias modifican penalizaciones/restricciones (capacidad reducida, bloqueos)
    sobre la matriz de adyacencia antes de resolver.

NOTA (Entrega 1): stub. `resolver_despacho` devuelve un itinerario base determinista
(sin OR-Tools) para que el pipeline corra end-to-end. El modelo MILP real va en Fase 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from engine.network import topology
from engine.optimizer.dispatch_plan import Despacho, DispatchPlan


@dataclass(frozen=True)
class RestriccionesFlota:
    """Recursos finitos que acotan el despacho."""

    flota_total: int
    conductores_disponibles: int
    capacidad_bus: int


def itinerario_base(ahora: datetime, norma_delta: float = 0.0) -> DispatchPlan:
    """
    Itinerario histórico precalculado (caso normal del gating, costo de CPU cero).

    Stub (Entrega 1): un despacho regular desde cada terminal.
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
    incidencias: list | None = None,
) -> DispatchPlan:
    """
    Resuelve el despacho óptimo con MILP bajo las restricciones dadas.

    Stub (Entrega 1): refuerza el itinerario base (más buses) y lo marca como `optimizado`.
    La construcción y resolución del modelo OR-Tools se implementa en Fase 3.
    """
    # TODO(Fase 3): construir y resolver el modelo MILP con OR-Tools (CBC).
    despachos = [
        Despacho(servicio="REG", terminal_salida=terminal, hora_salida=ahora, num_buses=3)
        for terminal in topology.TERMINALES
    ]
    return DispatchPlan(
        calculado_en=ahora,
        norma_delta=norma_delta,
        optimizado=True,
        despachos=despachos,
    )

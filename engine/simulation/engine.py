"""
Núcleo del simulador time-stepped state-space.

Estado por estación: `Q_s` = pasajeros en cola. En cada paso `Δt`:

    X_s   ~ Poisson(λ_s · Δt)                      (llegadas)
    E_s   = min(Q_s + X_s, capacidad_s · Δt)       (despeje: embarques)
    Q_s'  = Q_s + X_s − E_s                         (cola remanente)
    sat_s = Q_s' / aforo_s                          (saturación)

`simular_dia` corre el día en pasos de `dt_min` (por defecto 5 min) y **consolida a hora**: por
cada hora reporta llegadas, embarques, cola al cierre y la saturación máxima alcanzada en la hora.
Los destinos se muestrean con Multinomial sobre la OD del perfil (opcional, para reconstruir OD).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.network import topology
from engine.optimizer.dispatch_plan import DispatchPlan
from engine.simulation.config import RedConfig
from engine.simulation.demanda_perfil import PerfilDemanda
from engine.simulation.incidentes import Modificadores
from engine.simulation.plan_capacidad import capacidad_por_hora


def simulate_step(
    rng: np.random.Generator,
    q_prev: np.ndarray,
    lam_step: np.ndarray,
    cap_step: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Transición de estado de un paso. Devuelve (q_new, llegadas, embarques).

    `lam_step` y `cap_step` ya vienen escalados a la fracción de hora del paso.
    """
    llegadas = rng.poisson(np.maximum(lam_step, 0.0)).astype(float)
    embarques = np.minimum(q_prev + llegadas, np.maximum(cap_step, 0.0))
    q_new = q_prev + llegadas - embarques
    return q_new, llegadas, embarques


@dataclass(frozen=True)
class SimResult:
    """Resultado de un día simulado, consolidado por hora (24, N)."""

    llegadas: np.ndarray      # (24, N) pasajeros que llegaron por hora/estación
    embarques: np.ndarray     # (24, N) pasajeros embarcados
    cola: np.ndarray          # (24, N) cola al cierre de cada hora
    saturacion: np.ndarray    # (24, N) saturación máxima dentro de la hora (cola/aforo)
    aforo: np.ndarray         # (N,) aforo por estación
    od: np.ndarray | None = None  # (24, N, N) OD muestreada (si registrar_od=True)


def simular_dia(
    perfil: PerfilDemanda,
    plan_por_hora: dict[int, DispatchPlan] | DispatchPlan,
    config: RedConfig,
    mods: Modificadores | None = None,
    dt_min: int = 5,
    seed: int = 0,
    registrar_od: bool = False,
) -> SimResult:
    """Simula un día completo bajo un plan de despacho y (opcionalmente) modificadores."""
    mods = mods or Modificadores.vacio()
    rng = np.random.default_rng(seed)
    n = topology.N_ESTACIONES

    cap_h = capacidad_por_hora(plan_por_hora, config)   # (24, N) pasajeros/hora
    pasos = max(1, 60 // dt_min)
    frac = dt_min / 60.0

    llegadas = np.zeros((24, n))
    embarques = np.zeros((24, n))
    cola = np.zeros((24, n))
    saturacion = np.zeros((24, n))
    od = np.zeros((24, n, n)) if registrar_od else None

    q = np.zeros(n)
    for h in range(24):
        lam_h = perfil.lam[h] * mods.lam_factor[h] + mods.lam_extra[h]   # pasajeros/hora
        cap_eff = cap_h[h] * mods.cap_factor[h]                          # pasajeros/hora

        acc_arr = np.zeros(n)
        acc_srv = np.zeros(n)
        sat_max = np.zeros(n)
        for _ in range(pasos):
            q, arr, srv = simulate_step(rng, q, lam_h * frac, cap_eff * frac)
            acc_arr += arr
            acc_srv += srv
            sat_max = np.maximum(sat_max, q / config.aforo)

        llegadas[h] = acc_arr
        embarques[h] = acc_srv
        cola[h] = q
        saturacion[h] = sat_max

        if registrar_od is True and od is not None:
            for o in range(n):
                total = int(acc_arr[o])
                if total > 0:
                    od[h, o] = rng.multinomial(total, perfil.P[h, o])

    return SimResult(
        llegadas=llegadas, embarques=embarques, cola=cola,
        saturacion=saturacion, aforo=config.aforo, od=od,
    )

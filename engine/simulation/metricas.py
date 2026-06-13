"""
Métricas de saturación y colapso sobre un `SimResult`.

Traducen la simulación a indicadores accionables: dónde y cuándo se satura la red, cuánta gente
espera y si el sistema **colapsa** (saturación > 100% = la cola supera el aforo del andén).
"""

from __future__ import annotations

import numpy as np

from engine.network import topology
from engine.simulation.engine import SimResult

UMBRAL_COLAPSO = 1.0   # saturación ≥ 1 ⇒ la cola supera el aforo


def saturacion_max_por_estacion(res: SimResult) -> np.ndarray:
    """Saturación máxima del día por estación (N,)."""
    return res.saturacion.max(axis=0)


def cola_pico(res: SimResult) -> float:
    """Mayor cola observada en toda la red durante el día."""
    return float(res.cola.max())


def pasajeros_hora_espera(res: SimResult) -> float:
    """Pasajeros·hora acumulados en cola (área bajo la curva de cola, paso horario)."""
    return float(res.cola.sum())


def hay_colapso(res: SimResult, umbral: float = UMBRAL_COLAPSO) -> bool:
    """True si alguna estación supera el umbral de saturación en algún momento."""
    return bool((res.saturacion >= umbral).any())


def estaciones_en_colapso(res: SimResult, umbral: float = UMBRAL_COLAPSO) -> list[tuple[int, str]]:
    """Lista de (hora, estación) donde se supera el umbral de saturación."""
    horas, idxs = np.where(res.saturacion >= umbral)
    return [(int(h), topology.ESTACIONES[i]) for h, i in zip(horas, idxs)]


def resumen(res: SimResult, umbral: float = UMBRAL_COLAPSO) -> dict:
    """Resumen compacto del día simulado."""
    sat_est = saturacion_max_por_estacion(res)
    peor = int(sat_est.argmax())
    return {
        "saturacion_max": float(sat_est.max()),
        "estacion_mas_saturada": topology.ESTACIONES[peor],
        "cola_pico": cola_pico(res),
        "pasajeros_hora_espera": pasajeros_hora_espera(res),
        "colapso": hay_colapso(res, umbral),
        "n_eventos_colapso": int((res.saturacion >= umbral).sum()),
    }

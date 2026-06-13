"""
Estado de demanda combinado: M̂(t) = Mbase + ΔM(t).

Junta la línea base (`baseline`) con el residuo estimado (`residual`) y expone la norma
`‖ΔM(t)‖₂`, que es la señal de anomalía que consume el mecanismo de guarda (gating).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class EstadoDemanda:
    """Snapshot del estado de demanda en un instante t."""

    mbase: np.ndarray       # línea base (N, N)
    delta: np.ndarray       # residuo ΔM(t) (N, N)
    norma_delta: float      # ‖ΔM(t)‖₂

    @property
    def m_hat(self) -> np.ndarray:
        """Demanda estimada M̂(t) = Mbase + ΔM(t)."""
        return self.mbase + self.delta


def norma_l2(delta: np.ndarray) -> float:
    """Norma L2 (Frobenius) del residuo: magnitud global de la anomalía."""
    return float(np.linalg.norm(delta))


def construir_estado(mbase: np.ndarray, delta: np.ndarray) -> EstadoDemanda:
    """Ensambla el `EstadoDemanda` calculando la norma del residuo."""
    return EstadoDemanda(mbase=mbase, delta=delta, norma_delta=norma_l2(delta))

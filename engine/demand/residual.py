"""
Estimación del residuo ΔM(t) mediante Filtro de Kalman.

El estado de demanda se descompone en `M̂(t) = Mbase + ΔM(t)`. ΔM(t) captura la desviación
estocástica de la demanda observada respecto a la línea base histórica. Se estima con un
Filtro de Kalman sobre NumPy: predict/update por ventana, en microsegundos sobre CPU estándar
(sin GPU, sin entrenamiento pesado).

Se modela cada celda OD como un proceso escalar independiente (random walk + ruido de
observación), lo que reduce el filtro a operaciones vectorizadas sobre la matriz aplanada.

NOTA (Entrega 1): stub. `estimate` devuelve ΔM = (observado − Mbase) sin suavizado de Kalman.
El filtro completo (matrices Q/R, ganancia) se implementa en Fase 2.
"""

from __future__ import annotations

import numpy as np


class KalmanResidualEstimator:
    """
    Estimador de ΔM(t) por Filtro de Kalman, celda a celda.

    Args:
        q: varianza del proceso (qué tan rápido puede variar la demanda real).
        r: varianza de la observación (ruido del muestreo de torniquetes).
    """

    def __init__(self, q: float = 1.0, r: float = 10.0) -> None:
        self.q = q
        self.r = r
        self._estado: np.ndarray | None = None  # ΔM filtrado previo
        self._p: np.ndarray | None = None        # covarianza previa

    def reset(self) -> None:
        self._estado = None
        self._p = None

    def estimate(self, observado: np.ndarray, mbase: np.ndarray) -> np.ndarray:
        """
        Devuelve el residuo ΔM(t) dada la OD observada y la línea base.

        Stub (Entrega 1): residuo crudo sin filtrar.
        """
        # TODO(Fase 2): predict/update de Kalman vectorizado sobre las celdas.
        return observado - mbase

"""
Estimación del residuo ΔM(t) mediante Filtro de Kalman.

El estado de demanda se descompone en `M̂(t) = Mbase + ΔM(t)`. ΔM(t) captura la desviación
estocástica de la demanda observada respecto a la línea base histórica. Se estima con un
Filtro de Kalman sobre NumPy: predict/update por ventana, en microsegundos sobre CPU estándar
(sin GPU, sin entrenamiento pesado).

Cada celda OD se modela como un proceso escalar independiente:
  - estado (random walk):      x_t = x_{t-1} + ruido_proceso        (varianza q)
  - observación (residuo crudo): z_t = (observado_t − Mbase) = x_t + ruido_obs   (varianza r)

Esto reduce el filtro a operaciones vectorizadas sobre la matriz aplanada: el ruido de proceso
`q` controla qué tan rápido se deja seguir la demanda real; el de observación `r`, cuánto se
suaviza el muestreo ruidoso de torniquetes. Un `r` alto ⇒ más suavizado (filtra picos
espurios); un `q` alto ⇒ más reactivo a cambios reales.
"""

from __future__ import annotations

import numpy as np


class KalmanResidualEstimator:
    """Estimador de ΔM(t) por Filtro de Kalman escalar, celda a celda (vectorizado)."""

    def __init__(self, q: float = 1.0, r: float = 10.0) -> None:
        self.q = float(q)
        self.r = float(r)
        self._x: np.ndarray | None = None   # estado filtrado (ΔM) previo
        self._p: np.ndarray | None = None    # covarianza del estado previa

    def reset(self) -> None:
        """Reinicia el filtro (p.ej. al cambiar de día)."""
        self._x = None
        self._p = None

    def estimate(self, observado: np.ndarray, mbase: np.ndarray) -> np.ndarray:
        """
        Devuelve el residuo filtrado ΔM(t) dada la OD observada y la línea base.

        En la primera llamada inicializa el estado con la medición cruda; en las siguientes
        aplica el ciclo predict/update de Kalman.
        """
        z = observado - mbase  # medición: residuo crudo

        # Inicialización con la primera medición.
        if self._x is None or self._x.shape != z.shape:
            self._x = z.astype(float).copy()
            self._p = np.full(z.shape, self.r, dtype=float)
            return self._x.copy()

        # Predicción (random walk): el estado se mantiene, la incertidumbre crece.
        x_pred = self._x
        p_pred = self._p + self.q

        # Actualización con la medición.
        k = p_pred / (p_pred + self.r)   # ganancia de Kalman, por celda
        self._x = x_pred + k * (z - x_pred)
        self._p = (1.0 - k) * p_pred

        return self._x.copy()

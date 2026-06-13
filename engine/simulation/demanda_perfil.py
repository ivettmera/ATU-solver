"""
Perfil de demanda intradía que alimenta el simulador.

`PerfilDemanda` describe, por **hora del día**:
  - `lam[h, s]`  — llegadas esperadas (tasa) en la estación `s` durante la hora `h`.
  - `P[h, s, :]` — distribución de destinos de quien aborda en `s` (fila OD normalizada).

El motor muestrea las llegadas con Poisson sobre `lam` y los destinos con Multinomial sobre `P`.

Dos fuentes:
  - `sintetico(...)`        — perfil paramétrico con **picos bimodales** (mañana y tarde) y
    **direccionalidad** (mañana → centro/hubs, tarde → periferia). Corrige los dos defectos del
    generador de trip chaining actual (destinos uniformes, un solo pico).
  - `desde_mbase_intradia(...)` — perfil leído del tensor Mbase intradía `(24, N, N)` reconstruido
    de datos reales/sintéticos. Es el camino **real-data-ready**: solo cambia la fuente.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.network import topology

# Escala de demanda por tipo de día (relativa al día laboral).
ESCALA_TIPO_DIA: dict[str, float] = {
    "laboral": 1.0, "sabado": 0.6, "domingo": 0.4, "feriado": 0.3,
}


def _multiplicador_horario() -> np.ndarray:
    """Curva intradía bimodal (24,): picos mañana (07-09) y tarde (17-19), valle al mediodía."""
    horas = np.arange(24)
    pico_am = np.exp(-0.5 * ((horas - 8.0) / 1.1) ** 2)
    pico_pm = np.exp(-0.5 * ((horas - 18.0) / 1.3) ** 2)
    base = np.where((horas >= 5) & (horas <= 22), 0.12, 0.0)  # servicio diurno de fondo
    m = base + pico_am + 0.85 * pico_pm
    return m


def _pesos_estacion() -> np.ndarray:
    """Peso relativo de generación de viajes por estación (terminales y hubs concentran demanda)."""
    n = topology.N_ESTACIONES
    w = np.full(n, 1.0)
    for s in topology.SERVICIOS:
        if s.codigo != "REG":
            for i in s.indices_paradas():
                w[i] += 1.5            # hubs (parada de expreso) generan más
    for t in topology.TERMINALES:
        w[topology.INDICE_ESTACION[t]] += 2.0  # terminales, mucho más
    return w


def _zona_central() -> np.ndarray:
    """Peso de atracción del núcleo centro (alrededor de Estación Central)."""
    n = topology.N_ESTACIONES
    centro = topology.INDICE_ESTACION[topology.TERMINAL_CENTRAL]
    idx = np.arange(n)
    return np.exp(-0.5 * ((idx - centro) / 7.0) ** 2)


def _zona_periferia() -> np.ndarray:
    """Peso de atracción de la periferia (extremos norte y sur del corredor)."""
    centro = _zona_central()
    p = 1.0 - centro / centro.max()
    return p


@dataclass(frozen=True)
class PerfilDemanda:
    """Tasa de llegadas y distribución de destinos por hora."""

    lam: np.ndarray   # (24, N) llegadas esperadas/hora por estación
    P: np.ndarray     # (24, N, N) destino normalizado por (hora, origen)

    def od_hora(self, hora: int) -> np.ndarray:
        """Matriz OD esperada de una hora: `lam[h, o] * P[h, o, d]`."""
        return self.lam[hora][:, None] * self.P[hora]

    @classmethod
    def sintetico(
        cls,
        tipo_dia: str = "laboral",
        pico_llegadas: float = 1200.0,
    ) -> "PerfilDemanda":
        """
        Perfil paramétrico bimodal y direccional.

        Args:
            tipo_dia: escala la magnitud (laboral/sabado/domingo/feriado).
            pico_llegadas: llegadas/hora aproximadas en la estación más cargada en el pico.
        """
        n = topology.N_ESTACIONES
        escala = ESCALA_TIPO_DIA.get(tipo_dia, 1.0)

        m_h = _multiplicador_horario()                 # (24,)
        w_s = _pesos_estacion()                         # (N,)
        w_s = w_s / w_s.max()

        lam = escala * pico_llegadas * np.outer(m_h, w_s)   # (24, N)

        centro, periferia = _zona_central(), _zona_periferia()
        P = np.zeros((24, n, n))
        for h in range(24):
            # Mañana: destinos hacia el centro; tarde: hacia la periferia; mediodía: mezcla.
            if 5 <= h <= 11:
                atrac = centro
            elif 15 <= h <= 22:
                atrac = periferia
            else:
                atrac = 0.5 * centro + 0.5 * periferia
            fila = np.tile(atrac, (n, 1)).astype(float)
            np.fill_diagonal(fila, 0.0)                 # nadie viaja a su propia estación
            sumas = fila.sum(axis=1, keepdims=True)
            sumas[sumas == 0] = 1.0
            P[h] = fila / sumas
        return cls(lam=lam, P=P)

    @classmethod
    def desde_mbase_intradia(cls, tensor: np.ndarray) -> "PerfilDemanda":
        """
        Construye el perfil desde un tensor Mbase intradía `(24, N, N)` (datos reales/sintéticos).

        `lam[h, o] = Σ_d tensor[h, o, d]`  y  `P[h, o, :] = tensor[h, o, :] / lam[h, o]`.
        """
        if tensor.shape[0] != 24:
            raise ValueError(f"Se esperaba un tensor (24, N, N); llegó {tensor.shape}")
        lam = tensor.sum(axis=2)                         # (24, N)
        P = np.zeros_like(tensor, dtype=float)
        for h in range(24):
            sumas = lam[h][:, None]
            seguro = np.where(sumas == 0, 1.0, sumas)
            P[h] = tensor[h] / seguro
        return cls(lam=lam, P=P)

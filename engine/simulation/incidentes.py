"""
Modificadores de escenario e inyectores de incidentes.

`Modificadores` intercepta los parámetros base por hora antes de cada paso de simulación:
  - `cap_factor[h, s]` ∈ [0,1]  — fracción de capacidad de embarque disponible (1 = normal).
  - `lam_factor[h, s]`          — multiplicador de la tasa de llegadas (1 = normal).
  - `lam_extra[h, s]`           — llegadas adicionales/hora (picos exógenos, eventos).

Los inyectores cubren los casos de uso de contingencia:
  - `inject_transit_disruption` — bus malogrado/bloqueo en una estación: reduce su capacidad y
    **propaga represamiento** a las estaciones vecinas del corredor (backpressure, v1 simple).
  - `inject_external_event`     — concierto/partido: pico de llegadas concentrado en una estación.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.network import topology


@dataclass
class Modificadores:
    """Ajustes por hora a capacidad y llegadas. Mutable: los inyectores lo modifican in situ."""

    cap_factor: np.ndarray   # (24, N)
    lam_factor: np.ndarray   # (24, N)
    lam_extra: np.ndarray    # (24, N)

    @classmethod
    def vacio(cls) -> "Modificadores":
        n = topology.N_ESTACIONES
        return cls(
            cap_factor=np.ones((24, n)),
            lam_factor=np.ones((24, n)),
            lam_extra=np.zeros((24, n)),
        )


def inject_transit_disruption(
    mods: Modificadores,
    estacion: str,
    hora_inicio: int,
    duracion_h: int = 2,
    reduccion_pct: float = 70.0,
    propagacion: int = 3,
) -> Modificadores:
    """
    Reduce la capacidad de embarque en `estacion` durante la ventana y propaga represamiento.

    La estación afectada pierde `reduccion_pct`% de capacidad; las `propagacion` estaciones vecinas
    (a cada lado del corredor) pierden una fracción **decreciente** con la distancia, modelando la
    cola que se represa hacia las estaciones contiguas.
    """
    centro = topology.INDICE_ESTACION[estacion]
    n = topology.N_ESTACIONES
    red = min(max(reduccion_pct, 0.0), 100.0) / 100.0
    horas = [h % 24 for h in range(hora_inicio, hora_inicio + duracion_h)]

    for h in horas:
        mods.cap_factor[h, centro] *= (1.0 - red)
        for d in range(1, propagacion + 1):
            atenuado = red * (1.0 - d / (propagacion + 1))   # decae con la distancia
            for vecino in (centro - d, centro + d):
                if 0 <= vecino < n:
                    mods.cap_factor[h, vecino] *= (1.0 - atenuado)
    return mods


def inject_external_event(
    mods: Modificadores,
    estacion: str,
    hora_evento: int,
    afluencia: int,
    inbound: bool = True,
) -> Modificadores:
    """
    Pico exógeno de llegadas en `estacion` por un evento masivo.

    - `inbound=True`  (asistentes llegando): el pico se **reparte en las 2 h previas** al evento.
    - `inbound=False` (salida del evento): pico **concentrado en la hora siguiente** (~45 min).
    """
    idx = topology.INDICE_ESTACION[estacion]
    if inbound:
        horas = [(hora_evento - 2) % 24, (hora_evento - 1) % 24]
        for h in horas:
            mods.lam_extra[h, idx] += afluencia / 2.0
    else:
        mods.lam_extra[hora_evento % 24, idx] += afluencia
    return mods

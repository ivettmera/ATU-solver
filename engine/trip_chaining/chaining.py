"""
Trip Chaining — reconstrucción de la matriz Origen-Destino (OD).

El Metropolitano cobra solo al ingreso: no hay registro de salida, así que el destino de
cada viaje es latente. Se reconstruye por el **axioma de continuidad espaciotemporal**:

    destino(viaje_i) ≈ origen(viaje_{i+1})   del mismo usuario, el mismo día

y para el último viaje del día se aplica **cierre de lazo**:

    destino(último) ≈ origen(primero)        (el usuario regresa a su punto de partida)

Entrada: eventos de torniquete (tarjeta, timestamp, estación de ingreso).
Salida: matriz OD NxN (N = número de estaciones), indexada por `topology.ESTACIONES`.

NOTA (Entrega 1): este módulo es un stub. Devuelve una matriz de ceros con la forma correcta
para que el bucle de control corra end-to-end. La reconstrucción real se implementa en Fase 1.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import NamedTuple

import numpy as np

from engine.network import topology


class EventoViaje(NamedTuple):
    """Evento de ingreso a un torniquete (estructura interna, desacoplada de Pydantic)."""

    tarjeta_id: str
    timestamp: datetime
    estacion_origen: str


def reconstruir_od(eventos: Iterable[EventoViaje]) -> np.ndarray:
    """
    Reconstruye la matriz OD a partir de eventos de ingreso.

    Algoritmo (a implementar en Fase 1):
      1. Agrupar eventos por `tarjeta_id`.
      2. Ordenar cada grupo por `timestamp`.
      3. destino(i) = origen(i+1); último viaje → cierre de lazo al primer origen del día.
      4. Acumular cada par (origen, destino) en la celda OD[o][d].

    Returns:
        np.ndarray de forma (N, N) con conteos OD. Stub: ceros.
    """
    n = topology.N_ESTACIONES
    od = np.zeros((n, n), dtype=float)

    # TODO(Fase 1): implementar el encadenamiento real y el cierre de lazo.
    _ = list(eventos)  # consumir el iterable sin procesarlo todavía

    return od

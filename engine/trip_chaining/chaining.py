"""
Trip Chaining — reconstrucción de la matriz Origen-Destino (OD).

El Metropolitano cobra solo al ingreso: no hay registro de salida, así que el destino de
cada viaje es latente. Se reconstruye por el **axioma de continuidad espaciotemporal**:

    destino(viaje_i) ≈ origen(viaje_{i+1})   del mismo usuario, el mismo día

y para el último viaje del día se aplica **cierre de lazo**:

    destino(último) ≈ origen(primero)        (el usuario regresa a su punto de partida)

Entrada: eventos de torniquete (tarjeta, timestamp, estación de ingreso).
Salida: matriz OD NxN (N = número de estaciones), indexada por `topology.ESTACIONES`.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import NamedTuple

import numpy as np

from engine.network import topology

# Mínimo de viajes por tarjeta para poder inferir un destino encadenado.
MIN_VIAJES = 2


class EventoViaje(NamedTuple):
    """Evento de ingreso a un torniquete (estructura interna, desacoplada de Pydantic)."""

    tarjeta_id: str
    timestamp: datetime
    estacion_origen: str


def reconstruir_od(eventos: Iterable[EventoViaje]) -> np.ndarray:
    """
    Reconstruye la matriz OD a partir de eventos de ingreso (cobro abierto, sin salidas).

    Algoritmo:
      1. Agrupar eventos por `tarjeta_id`.
      2. Ordenar cada grupo por `timestamp`.
      3. destino(viaje_i) = origen(viaje_{i+1}).
      4. Cierre de lazo: destino(último) = origen(primero) del día.
      5. Acumular cada par (origen, destino) en OD[o][d].

    Las tarjetas con menos de `MIN_VIAJES` ingresos se descartan: con un solo viaje no hay
    "siguiente origen" ni lazo significativo, así que su destino es indeterminable.

    Returns:
        np.ndarray de forma (N, N) con los conteos OD reconstruidos.
    """
    n = topology.N_ESTACIONES
    od = np.zeros((n, n), dtype=float)

    # 1. Agrupar por tarjeta.
    por_tarjeta: dict[str, list[EventoViaje]] = defaultdict(list)
    for ev in eventos:
        por_tarjeta[ev.tarjeta_id].append(ev)

    for viajes in por_tarjeta.values():
        if len(viajes) < MIN_VIAJES:
            continue

        # 2. Ordenar cronológicamente.
        viajes.sort(key=lambda e: e.timestamp)

        indices = [topology.INDICE_ESTACION[v.estacion_origen] for v in viajes]

        # 3. Encadenamiento: destino(i) = origen(i+1).
        for o, d in zip(indices, indices[1:]):
            od[o, d] += 1.0

        # 4. Cierre de lazo: destino(último) = origen(primero).
        od[indices[-1], indices[0]] += 1.0

    return od

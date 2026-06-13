"""
Generador de eventos de torniquete sintéticos con destino ground-truth.

Sirve para validar el trip chaining: como el sistema real solo registra ingresos, aquí
fabricamos cadenas de viajes por usuario donde SÍ conocemos el destino real de cada viaje,
y devolvemos en paralelo la matriz OD verdadera. Así se puede medir qué tan bien
`reconstruir_od` recupera la OD a partir de solo los ingresos.

Modelo de movilidad (simplificado pero fiel al axioma de continuidad):
  - Cada tarjeta hace una cadena de `k` viajes en el día (k≥2).
  - El usuario sale de donde llegó: el ingreso del viaje i+1 es el destino real del viaje i.
  - Último viaje: con probabilidad `prob_cierre` regresa al primer origen (cierre de lazo);
    si no, termina en otra estación (usuario que no cierra el lazo ese día).
  - Las tarjetas con un solo viaje no aportan información de destino (se modelan aparte).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from engine.network import topology
from engine.trip_chaining.chaining import EventoViaje


def generar_dia(
    n_usuarios: int = 500,
    semilla: int = 42,
    prob_cierre: float = 0.85,
    fecha: datetime | None = None,
) -> tuple[list[EventoViaje], np.ndarray]:
    """
    Genera los eventos de ingreso de un día y la matriz OD ground-truth.

    Args:
        n_usuarios: número de tarjetas (usuarios) a simular.
        semilla: semilla del RNG para reproducibilidad.
        prob_cierre: probabilidad de que el último viaje cierre el lazo al primer origen.
        fecha: día base (UTC) para los timestamps; por defecto, hoy.

    Returns:
        (eventos, od_groundtruth):
          - eventos: lista de EventoViaje (solo ingresos), en orden arbitrario.
          - od_groundtruth: matriz (N, N) con los conteos OD reales.
    """
    rng = np.random.default_rng(semilla)
    n = topology.N_ESTACIONES
    od = np.zeros((n, n), dtype=float)
    eventos: list[EventoViaje] = []

    base = fecha or datetime.now(timezone.utc)
    base = base.replace(hour=0, minute=0, second=0, microsecond=0)

    for u in range(n_usuarios):
        k = int(rng.integers(2, 4))  # 2 o 3 viajes

        # Secuencia de paradas distintas que el usuario visita en orden.
        paradas = rng.choice(n, size=k + 1, replace=False)

        # Hora de inicio (pico mañana) y separación entre viajes.
        hora = float(rng.normal(7.5, 1.0))
        for i in range(k):
            origen = int(paradas[i])

            # Destino real del viaje i.
            if i < k - 1:
                destino = int(paradas[i + 1])
            else:
                # Último viaje: cierre de lazo o estación distinta.
                if rng.random() < prob_cierre:
                    destino = int(paradas[0])
                else:
                    destino = int(paradas[k])  # parada extra reservada → no cierra lazo

            ts = base + timedelta(hours=min(max(hora, 0.0), 23.99))
            eventos.append(
                EventoViaje(
                    tarjeta_id=f"TARJ-{u:05d}",
                    timestamp=ts,
                    estacion_origen=topology.ESTACIONES[origen],
                )
            )
            od[origen, destino] += 1.0
            hora += float(rng.uniform(3.0, 6.0))  # siguiente viaje, horas después

    # Mezclar para no entregar los eventos ya ordenados por tarjeta/tiempo.
    rng.shuffle(eventos)
    return eventos, od

"""
Construcción de Mbase a partir de un histórico sintético.

Genera varios días sintéticos por tipo de día, reconstruye la OD diaria de cada uno con el
mismo trip chaining que corre en producción, y los promedia en `Mbase[tipo_día]`. Esto imita
el cálculo offline trimestral; al migrar a datos reales, solo cambia la fuente de los días.

Los niveles de demanda por tipo de día reflejan el patrón real del Metropolitano: máximo en
día laboral y decreciente en fin de semana y feriados.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from engine.demand import baseline
from engine.trip_chaining import synthetic
from engine.trip_chaining.chaining import EventoViaje, reconstruir_od, reconstruir_od_por_hora

# Usuarios (tarjetas) simulados por día según el tipo de día.
NIVEL_DEMANDA: dict[str, int] = {
    "laboral": 500,
    "sabado": 320,
    "domingo": 220,
    "feriado": 150,
}


def construir_mbase_sintetico(
    dias_por_tipo: int = 20,
    semilla: int = 0,
) -> dict[str, np.ndarray]:
    """
    Genera el histórico sintético y devuelve `Mbase[tipo_día]`.

    Args:
        dias_por_tipo: número de días históricos a simular por cada tipo de día.
        semilla: semilla base; cada día usa una semilla derivada distinta.

    Returns:
        tipo_día → matriz Mbase promedio.
    """
    ods_por_tipo: dict[str, list[np.ndarray]] = {tipo: [] for tipo in baseline.TIPOS_DIA}

    contador = semilla
    for tipo_dia in baseline.TIPOS_DIA:
        n_usuarios = NIVEL_DEMANDA[tipo_dia]
        for _ in range(dias_por_tipo):
            eventos, _ = synthetic.generar_dia(n_usuarios=n_usuarios, semilla=contador)
            ods_por_tipo[tipo_dia].append(reconstruir_od(eventos))
            contador += 1

    return baseline.build_baseline(ods_por_tipo)


def construir_mbase_desde_eventos(eventos: list[EventoViaje]) -> dict[str, np.ndarray]:
    """
    Construye Mbase a partir de eventos reales/por-tarjeta (p.ej. cargados de CSV).

    Agrupa los eventos por **fecha** (un día = una OD reconstruida, para no encadenar viajes
    entre días distintos), clasifica cada día por tipo y promedia las OD por tipo de día.
    Este es el camino que se usará con los datos reales: solo cambia la fuente de los eventos.
    """
    por_fecha: dict[object, list[EventoViaje]] = defaultdict(list)
    for ev in eventos:
        por_fecha[ev.timestamp.date()].append(ev)

    ods_por_tipo: dict[str, list[np.ndarray]] = {tipo: [] for tipo in baseline.TIPOS_DIA}
    for fecha, eventos_dia in por_fecha.items():
        tipo_dia = baseline.clasificar_dia(fecha)
        ods_por_tipo[tipo_dia].append(reconstruir_od(eventos_dia))

    return baseline.build_baseline(ods_por_tipo)


# ── Mbase intradía: tipo_día → tensor (24, N, N) ─────────────────────────────────────────
def construir_mbase_intradia_sintetico(
    dias_por_tipo: int = 20,
    semilla: int = 0,
) -> dict[str, np.ndarray]:
    """Igual que `construir_mbase_sintetico` pero desagregado por hora de abordaje (24, N, N)."""
    tensores_por_tipo: dict[str, list[np.ndarray]] = {tipo: [] for tipo in baseline.TIPOS_DIA}

    contador = semilla
    for tipo_dia in baseline.TIPOS_DIA:
        n_usuarios = NIVEL_DEMANDA[tipo_dia]
        for _ in range(dias_por_tipo):
            eventos, _ = synthetic.generar_dia(n_usuarios=n_usuarios, semilla=contador)
            tensores_por_tipo[tipo_dia].append(reconstruir_od_por_hora(eventos))
            contador += 1

    return baseline.build_baseline_intradia(tensores_por_tipo)


def construir_mbase_intradia_desde_eventos(eventos: list[EventoViaje]) -> dict[str, np.ndarray]:
    """Mbase intradía (24, N, N) por tipo de día a partir de eventos reales/por-tarjeta."""
    por_fecha: dict[object, list[EventoViaje]] = defaultdict(list)
    for ev in eventos:
        por_fecha[ev.timestamp.date()].append(ev)

    tensores_por_tipo: dict[str, list[np.ndarray]] = {tipo: [] for tipo in baseline.TIPOS_DIA}
    for fecha, eventos_dia in por_fecha.items():
        tipo_dia = baseline.clasificar_dia(fecha)
        tensores_por_tipo[tipo_dia].append(reconstruir_od_por_hora(eventos_dia))

    return baseline.build_baseline_intradia(tensores_por_tipo)

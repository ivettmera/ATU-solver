"""
Construcción de Mbase a partir de un histórico sintético.

Genera varios días sintéticos por tipo de día, reconstruye la OD diaria de cada uno con el
mismo trip chaining que corre en producción, y los promedia en `Mbase[tipo_día]`. Esto imita
el cálculo offline trimestral; al migrar a datos reales, solo cambia la fuente de los días.

Los niveles de demanda por tipo de día reflejan el patrón real del Metropolitano: máximo en
día laboral y decreciente en fin de semana y feriados.
"""

from __future__ import annotations

import numpy as np

from engine.demand import baseline
from engine.trip_chaining import synthetic
from engine.trip_chaining.chaining import reconstruir_od

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

"""
Línea base de demanda (Mbase).

`Mbase[tipo_día]` es la matriz OD diaria esperada para cada tipo de día, calculada **offline**
promediando las matrices OD reconstruidas de varios días históricos del mismo tipo. En runtime
se sirve desde caché (Redis) con costo O(1): es el itinerario histórico sobre el que se aplica
el residuo ΔM(t).

Decisión de diseño: Mbase se indexa por **tipo de día** (laboral/sábado/domingo/feriado) y no
por bloque intradía, porque el trip chaining es intrínsecamente diario (necesita el día completo
para cerrar lazos). El scheduler acumula las ventanas vigentes del día y compara la OD diaria en
curso contra el patrón histórico del tipo de día correspondiente. La granularidad intradía queda
como refinamiento futuro.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import numpy as np

from engine.network import topology

# Tipos de día reconocidos.
TIPOS_DIA: list[str] = ["laboral", "sabado", "domingo", "feriado"]

# Feriados nacionales del Perú (mm-dd), independientes del año.
FERIADOS_PERU: set[str] = {
    "01-01", "05-01", "06-29", "07-28", "07-29",
    "08-30", "10-08", "11-01", "12-08", "12-25",
}


def clasificar_dia(fecha: date | datetime) -> str:
    """Devuelve el tipo de día (laboral/sabado/domingo/feriado) de una fecha."""
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    if fecha.strftime("%m-%d") in FERIADOS_PERU:
        return "feriado"
    dow = fecha.weekday()  # 0=lunes ... 6=domingo
    if dow == 6:
        return "domingo"
    if dow == 5:
        return "sabado"
    return "laboral"


def clave_baseline(tipo_dia: str) -> str:
    """Clave canónica para cachear/leer la matriz Mbase de un tipo de día (p.ej. en Redis)."""
    return f"mbase:{tipo_dia}"


def build_baseline(ods_por_tipo: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    """
    Promedia las matrices OD reconstruidas, agrupadas por tipo de día.

    Args:
        ods_por_tipo: tipo_día → lista de matrices OD observadas (una por día histórico).

    Returns:
        tipo_día → matriz Mbase promedio. Los tipos sin observaciones se omiten.
    """
    mbase: dict[str, np.ndarray] = {}
    for tipo_dia, ods in ods_por_tipo.items():
        if not ods:
            continue
        mbase[tipo_dia] = np.mean(np.stack(ods, axis=0), axis=0)
    return mbase


def matriz_a_json(matriz: np.ndarray) -> str:
    """Serializa una matriz OD a JSON (lista de listas) para Redis."""
    return json.dumps(matriz.tolist())


def matriz_desde_json(texto: str) -> np.ndarray:
    """Deserializa una matriz OD desde el JSON almacenado en Redis."""
    return np.asarray(json.loads(texto), dtype=float)


def matriz_vacia() -> np.ndarray:
    """Matriz OD de ceros con la forma del corredor (fallback cuando no hay Mbase)."""
    n = topology.N_ESTACIONES
    return np.zeros((n, n), dtype=float)

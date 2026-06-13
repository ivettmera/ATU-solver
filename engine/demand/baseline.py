"""
Línea base de demanda (Mbase).

`Mbase[tipo_día][bloque]` es una matriz OD promedio calculada **offline** (trimestralmente)
a partir de las matrices OD reconstruidas por trip chaining. En runtime se sirve desde caché
(Redis) con costo O(1): es el itinerario histórico sobre el que se aplica el residuo ΔM(t).

`tipo_día` ∈ {laboral, sabado, domingo, feriado}; `bloque` es el índice de la ventana
temporal del día (p.ej. bloques de 5 min → 288 bloques).

NOTA (Entrega 1): stub. `build_baseline` devuelve ceros; la persistencia real en Redis y el
cálculo a partir de datos sintéticos se implementan en Fase 2.
"""

from __future__ import annotations

import numpy as np

from engine.network import topology

TIPOS_DIA: list[str] = ["laboral", "sabado", "domingo", "feriado"]


def clave_baseline(tipo_dia: str, bloque: int) -> str:
    """Clave canónica para cachear/leer una matriz Mbase (p.ej. en Redis)."""
    return f"mbase:{tipo_dia}:{bloque}"


def build_baseline(od_por_clave: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    """
    Promedia las matrices OD reconstruidas, agrupadas por (tipo_día, bloque).

    Args:
        od_por_clave: clave canónica → lista de matrices OD observadas en esa categoría.

    Returns:
        clave canónica → matriz Mbase promedio.

    Stub (Entrega 1): devuelve una matriz de ceros por clave.
    """
    n = topology.N_ESTACIONES
    # TODO(Fase 2): Mbase = media de las OD observadas por categoría.
    return {clave: np.zeros((n, n), dtype=float) for clave in od_por_clave}


def matriz_vacia() -> np.ndarray:
    """Matriz OD de ceros con la forma del corredor (fallback cuando no hay Mbase)."""
    n = topology.N_ESTACIONES
    return np.zeros((n, n), dtype=float)

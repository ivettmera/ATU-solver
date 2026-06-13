"""
Caché en memoria de la línea base Mbase.

Mbase se calcula offline y se persiste en Redis (`scripts/seed_baseline.py`). Al arrancar la
app se carga una vez a memoria para servirla en O(1) en cada ciclo del scheduler, sin pegarle
a Redis cada 5 min. La clave es el tipo de día (laboral/sábado/domingo/feriado).
"""

from __future__ import annotations

import numpy as np
from redis.asyncio import Redis

from engine.demand import baseline

_mbase: dict[str, np.ndarray] = {}
_mbase_intradia: dict[str, np.ndarray] = {}


async def cargar_mbase(redis: Redis) -> int:
    """
    Carga Mbase (diaria e intradía) desde Redis a memoria. Devuelve cuántos tipos de día con
    Mbase diaria se cargaron.
    """
    _mbase.clear()
    _mbase_intradia.clear()
    for tipo_dia in baseline.TIPOS_DIA:
        crudo = await redis.get(baseline.clave_baseline(tipo_dia))
        if crudo is not None:
            _mbase[tipo_dia] = baseline.matriz_desde_json(crudo)
        crudo_intradia = await redis.get(baseline.clave_baseline_intradia(tipo_dia))
        if crudo_intradia is not None:
            _mbase_intradia[tipo_dia] = baseline.matriz_desde_json(crudo_intradia)
    return len(_mbase)


def obtener_mbase(tipo_dia: str) -> np.ndarray:
    """
    Mbase diaria del tipo de día indicado. Si no está cargada (no se sembró), devuelve una matriz
    de ceros: el sistema degrada con elegancia operando como si todo fuese residuo.
    """
    return _mbase.get(tipo_dia, baseline.matriz_vacia())


def obtener_mbase_intradia(tipo_dia: str) -> np.ndarray:
    """Tensor Mbase intradía (24, N, N) del tipo de día; ceros si no se sembró."""
    return _mbase_intradia.get(tipo_dia, baseline.tensor_vacio_intradia())


def hay_mbase() -> bool:
    return len(_mbase) > 0


def hay_mbase_intradia() -> bool:
    return len(_mbase_intradia) > 0

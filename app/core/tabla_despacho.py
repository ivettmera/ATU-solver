"""
Caché en memoria de la tabla de despacho precalculada.

La tabla se calcula offline (`scripts/seed_baseline.py`) y se persiste en Redis. Al arrancar la app
se carga una vez a memoria; el ciclo de control la consulta en O(1) para servir el plan base
pico-consciente de la hora actual, sin recalcular el MILP cuando el gating no se dispara.
"""

from __future__ import annotations

from datetime import datetime

from redis.asyncio import Redis

from engine.optimizer import precompute
from engine.optimizer.dispatch_plan import DispatchPlan

_tabla: dict[str, dict[int, list[dict]]] = {}


async def cargar_tabla(redis: Redis) -> int:
    """Carga la tabla desde Redis a memoria. Devuelve cuántos tipos de día tienen plan."""
    _tabla.clear()
    crudo = await redis.get(precompute.CLAVE_TABLA)
    if crudo is not None:
        _tabla.update(precompute.tabla_desde_json(crudo))
    return len(_tabla)


def hay_tabla() -> bool:
    return len(_tabla) > 0


def plan_para(
    tipo_dia: str,
    hora: int,
    ahora: datetime,
    norma_delta: float = 0.0,
) -> DispatchPlan | None:
    """
    Plan precalculado para `(tipo_día, hora)`, materializado con la hora actual.

    Devuelve `None` si no hay tabla cargada o falta la hora (el caso base cae al itinerario fijo).
    """
    por_hora = _tabla.get(tipo_dia)
    if not por_hora or hora not in por_hora:
        return None
    return precompute.materializar_plan(por_hora[hora], ahora, norma_delta)

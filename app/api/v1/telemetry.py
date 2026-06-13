"""
Ingesta de telemetría — POST /api/v1/telemetry/ingress.

Recibe los eventos crudos de los torniquetes (cada ~5 min) y los almacena de forma atómica
en Redis, agrupados por ventana temporal. El procesamiento (trip chaining, optimización) lo
hace el scheduler de forma asíncrona; este endpoint solo persiste rápido y responde.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.v1.schemas import IngressResponse, TelemetryPayload
from app.core.config import Settings, get_settings
from app.core.redis_client import get_redis

router = APIRouter(prefix="/telemetry", tags=["Ingesta"])


def _clave_ventana(settings: Settings, ts) -> str:
    """Clave de Redis para la ventana de `BLOQUE_MIN` minutos que contiene `ts`."""
    minuto_bloque = (ts.minute // settings.BLOQUE_MIN) * settings.BLOQUE_MIN
    sello = ts.strftime("%Y%m%dT%H") + f"{minuto_bloque:02d}"
    return f"{settings.PREFIX_TELEMETRIA}:{sello}"


@router.post("/ingress", response_model=IngressResponse)
async def ingress(
    payload: TelemetryPayload,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> IngressResponse:
    clave = _clave_ventana(settings, payload.timestamp_envio)

    # Almacenamiento atómico: RPUSH de cada evento serializado en la lista de la ventana.
    if payload.eventos:
        pipe = redis.pipeline()
        for ev in payload.eventos:
            pipe.rpush(clave, ev.model_dump_json())
        # Las ventanas expiran solas; definen la ventana móvil de comparación con Mbase.
        pipe.expire(clave, settings.VENTANA_TELEMETRIA_MIN * 60)
        await pipe.execute()

    return IngressResponse(eventos_recibidos=len(payload.eventos), ventana=clave)

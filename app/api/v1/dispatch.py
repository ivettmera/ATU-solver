"""
Consumo de decisiones — GET /api/v1/dispatch/recommendations y WS /api/v1/dispatch/stream.

  - REST (pull): devuelve el último plan de despacho calculado, cacheado en Redis.
  - WebSocket (push): conexión dúplex que recibe los planes apenas el motor termina de
    calcular uno nuevo (difundidos por el `ConnectionManager` desde el scheduler).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.api.v1.schemas import DispatchPlan
from app.core.config import Settings, get_settings
from app.core.redis_client import get_redis
from app.ws.connection_manager import manager
from engine.optimizer.milp import itinerario_base

router = APIRouter(prefix="/dispatch", tags=["Despacho"])


@router.get("/recommendations", response_model=DispatchPlan)
async def recomendaciones(
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> DispatchPlan:
    """Último `DispatchPlan` calculado. Si aún no hay ninguno, devuelve el itinerario base."""
    crudo = await redis.get(settings.KEY_PLAN_ACTUAL)
    if crudo is not None:
        return DispatchPlan.model_validate(json.loads(crudo))

    # Todavía no corrió el scheduler: responder el itinerario base como fallback seguro.
    plan = itinerario_base(datetime.now(timezone.utc))
    return DispatchPlan.desde_engine(plan)


@router.websocket("/stream")
async def stream(websocket: WebSocket) -> None:
    """Registra el cliente y le empuja cada nuevo plan hasta que se desconecta."""
    await manager.connect(websocket)
    try:
        while True:
            # No esperamos mensajes del cliente; mantenemos viva la conexión.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)

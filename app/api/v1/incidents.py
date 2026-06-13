"""
Control de incidencias — POST /api/v1/incidents.

Registra bloqueos de vías, accidentes o andenes colapsados reportados manualmente. Una
incidencia modifica las restricciones/penalizaciones del optimizador y, según su severidad,
fuerza un recálculo MILP inmediato en el siguiente ciclo (rompe el gating sin esperar a ε).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.v1.schemas import IncidentReport, IncidentResponse
from app.core.config import Settings, get_settings
from app.core.redis_client import get_redis

router = APIRouter(prefix="/incidents", tags=["Incidencias"])

# Severidades que disparan recálculo inmediato del despacho.
_SEVERIDADES_CRITICAS = {"MEDIA", "ALTA"}


@router.post("", response_model=IncidentResponse)
async def reportar_incidencia(
    incidente: IncidentReport,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> IncidentResponse:
    # Se indexan por estación en un hash de incidencias activas que el optimizador consulta.
    await redis.hset(
        settings.KEY_INCIDENCIAS,
        incidente.estacion_id,
        incidente.model_dump_json(),
    )

    recalculo = incidente.bloqueado or incidente.severidad in _SEVERIDADES_CRITICAS
    return IncidentResponse(estacion_id=incidente.estacion_id, recalculo_forzado=recalculo)

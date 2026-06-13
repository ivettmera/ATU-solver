"""
Control de incidencias — /api/v1/incidents.

Registra bloqueos de vías, accidentes o andenes colapsados reportados manualmente. Una
incidencia modifica las restricciones/penalizaciones del optimizador (degrada la capacidad
efectiva de las rutas afectadas) y, según su severidad, fuerza un recálculo MILP inmediato.

Cada incidencia se guarda en su propia clave con TTL: si operaciones no la refresca, se
**auto-resuelve** al expirar; también puede resolverse explícitamente con DELETE.

  POST   /incidents                  → registrar/refrescar una incidencia
  GET    /incidents                  → listar incidencias activas
  DELETE /incidents/{estacion_id}    → resolver una incidencia
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from app.api.v1.schemas import (
    IncidentReport,
    IncidentResolvedResponse,
    IncidentResponse,
)
from app.core.config import Settings, get_settings
from app.core.redis_client import get_redis

router = APIRouter(prefix="/incidents", tags=["Incidencias"])

# Severidades que disparan recálculo inmediato del despacho.
_SEVERIDADES_CRITICAS = {"MEDIA", "ALTA"}


def _clave(settings: Settings, estacion_id: str) -> str:
    return f"{settings.PREFIX_INCIDENCIA}:{estacion_id}"


@router.post("", response_model=IncidentResponse)
async def reportar_incidencia(
    incidente: IncidentReport,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> IncidentResponse:
    # Una clave por estación con TTL: el optimizador la consulta y se auto-resuelve al expirar.
    await redis.set(
        _clave(settings, incidente.estacion_id),
        incidente.model_dump_json(),
        ex=settings.INCIDENCIA_TTL_SEG,
    )
    recalculo = incidente.bloqueado or incidente.severidad in _SEVERIDADES_CRITICAS
    return IncidentResponse(
        estacion_id=incidente.estacion_id,
        recalculo_forzado=recalculo,
        expira_en_seg=settings.INCIDENCIA_TTL_SEG,
    )


@router.get("", response_model=list[IncidentReport])
async def listar_incidencias(
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> list[IncidentReport]:
    incidencias: list[IncidentReport] = []
    async for clave in redis.scan_iter(match=f"{settings.PREFIX_INCIDENCIA}:*"):
        valor = await redis.get(clave)
        if valor is not None:
            incidencias.append(IncidentReport.model_validate(json.loads(valor)))
    return incidencias


@router.delete("/{estacion_id}", response_model=IncidentResolvedResponse)
async def resolver_incidencia(
    estacion_id: str,
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> IncidentResolvedResponse:
    eliminado = await redis.delete(_clave(settings, estacion_id))
    estado = "resuelta" if eliminado else "inexistente"
    return IncidentResolvedResponse(estado=estado, estacion_id=estacion_id)

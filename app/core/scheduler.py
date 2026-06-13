"""
Planificador asíncrono del bucle de control (APScheduler).

Cada `INTERVALO_OPT_SEG` segundos ejecuta el ciclo de despacho. El cableado completo está
presente desde la Entrega 1; los pasos matemáticos usan los stubs del `engine/` (que corren
end-to-end con datos mock) y se irán rellenando en las fases siguientes.

Flujo del job:
  1. leer la ventana de telemetría desde Redis,
  2. trip chaining → matriz OD observada,
  3. demanda → ΔM(t) (Kalman) y ‖ΔM‖₂,
  4. gating → ¿optimizar?,
  5. itinerario base | MILP → DispatchPlan,
  6. persistir el plan en Redis y difundirlo por WebSocket si cambió.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis

from app.api.v1.schemas import DispatchPlan as DispatchPlanAPI
from app.core.config import Settings, get_settings
from app.core.redis_client import get_redis
from app.ws.connection_manager import manager
from engine.demand import baseline, state
from engine.demand.residual import KalmanResidualEstimator
from engine.optimizer import gating, milp
from engine.trip_chaining.chaining import EventoViaje, reconstruir_od

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_estimador = KalmanResidualEstimator()


async def _leer_eventos_recientes(redis: Redis, settings: Settings) -> list[EventoViaje]:
    """
    Lee las ventanas de telemetría vigentes en Redis y las convierte a EventoViaje.

    Las ventanas son listas (`RPUSH` desde el endpoint de ingesta) que expiran solas, así que
    solo quedan las recientes; se barren todas las que coincidan con el prefijo.
    """
    eventos: list[EventoViaje] = []
    async for clave in redis.scan_iter(match=f"{settings.PREFIX_TELEMETRIA}:*"):
        crudos = await redis.lrange(clave, 0, -1)
        for crudo in crudos:
            ev = json.loads(crudo)
            eventos.append(
                EventoViaje(
                    tarjeta_id=ev["tarjeta_id"],
                    timestamp=datetime.fromisoformat(ev["timestamp_entrada"]),
                    estacion_origen=ev["estacion_origen"],
                )
            )
    return eventos


async def _ciclo_despacho() -> None:
    """Una iteración del bucle de control (ver docstring del módulo)."""
    settings = get_settings()
    redis = get_redis()
    ahora = datetime.now(timezone.utc)

    # 1. Telemetría vigente en Redis → eventos de ingreso.
    eventos = await _leer_eventos_recientes(redis, settings)

    # 2. Trip chaining → OD observada.
    od_observada = reconstruir_od(eventos)

    # 3. Demanda: Mbase (stub vacío) + residuo ΔM(t).
    mbase = baseline.matriz_vacia()
    delta = _estimador.estimate(od_observada, mbase)
    estado = state.construir_estado(mbase, delta)

    # 4. Gating.
    incidencias = await redis.exists(settings.KEY_INCIDENCIAS)
    optimizar = gating.debe_optimizar(estado.norma_delta, settings.EPSILON, bool(incidencias))

    # 5. Plan: itinerario base o MILP.
    if optimizar:
        plan_engine = milp.resolver_despacho(
            ahora=ahora,
            m_hat=estado.m_hat,
            restricciones=milp.RestriccionesFlota(
                flota_total=settings.FLOTA_TOTAL,
                conductores_disponibles=settings.CONDUCTORES_DISPONIBLES,
                capacidad_bus=settings.CAPACIDAD_BUS,
            ),
            norma_delta=estado.norma_delta,
        )
    else:
        plan_engine = milp.itinerario_base(ahora, estado.norma_delta)

    plan_api = DispatchPlanAPI.desde_engine(plan_engine)
    payload = plan_api.model_dump(mode="json")

    # 6. Persistir y difundir.
    await redis.set(settings.KEY_PLAN_ACTUAL, json.dumps(payload))
    await manager.broadcast_json(payload)
    logger.info(
        "Ciclo de despacho: eventos=%d optimizado=%s norma=%.2f clientes=%d",
        len(eventos), plan_engine.optimizado, estado.norma_delta, manager.total,
    )


def start_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Crea y arranca el scheduler con el job de despacho periódico."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.add_job(
            _ciclo_despacho,
            trigger="interval",
            seconds=settings.INTERVALO_OPT_SEG,
            id="ciclo_despacho",
            replace_existing=True,
            max_instances=1,
        )
        _scheduler.start()
        logger.info("Scheduler iniciado (cada %ds)", settings.INTERVALO_OPT_SEG)
    return _scheduler


def stop_scheduler() -> None:
    """Detiene el scheduler de forma ordenada."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

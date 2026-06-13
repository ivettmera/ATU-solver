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
from app.core.mbase_cache import obtener_mbase
from app.core.redis_client import get_redis
from app.ws.connection_manager import manager
from engine.demand import baseline, state
from engine.demand.residual import KalmanResidualEstimator
from engine.optimizer import gating, milp
from engine.trip_chaining.chaining import EventoViaje, reconstruir_od

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_estimador = KalmanResidualEstimator()
# Firma del último plan difundido por WebSocket (para emitir solo ante cambios).
_ultima_firma: tuple | None = None


def _firma_plan(payload: dict) -> tuple:
    """
    Firma estable de la *decisión* de un plan, ignorando el timestamp.

    Dos planes con las mismas recomendaciones y el mismo flag `optimizado` tienen la misma
    firma aunque se hayan calculado en instantes distintos: así no se difunde un plan idéntico
    cada 5 min.
    """
    recs = sorted(
        (r["servicio"], r["terminal_salida"], r["num_buses"])
        for r in payload["recomendaciones"]
    )
    return (payload["optimizado"], tuple(recs))


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


async def _leer_incidencias(redis: Redis, settings: Settings) -> list[milp.IncidenciaOperativa]:
    """Lee el hash de incidencias activas y las convierte a incidencias operativas del MILP."""
    crudas = await redis.hgetall(settings.KEY_INCIDENCIAS)
    incidencias: list[milp.IncidenciaOperativa] = []
    for valor in crudas.values():
        inc = json.loads(valor)
        incidencias.append(
            milp.IncidenciaOperativa(
                estacion=inc["estacion_id"],
                bloqueado=inc.get("bloqueado", False),
                capacidad_reducida_pct=inc.get("capacidad_reducida_porcentaje", 0.0),
            )
        )
    return incidencias


async def _ciclo_despacho() -> None:
    """Una iteración del bucle de control (ver docstring del módulo)."""
    settings = get_settings()
    redis = get_redis()
    ahora = datetime.now(timezone.utc)

    # 1. Telemetría vigente en Redis → eventos de ingreso.
    eventos = await _leer_eventos_recientes(redis, settings)

    # 2. Trip chaining → OD observada.
    od_observada = reconstruir_od(eventos)

    # 3. Demanda: Mbase del tipo de día actual + residuo ΔM(t) filtrado por Kalman.
    tipo_dia = baseline.clasificar_dia(ahora)
    mbase = obtener_mbase(tipo_dia)
    delta = _estimador.estimate(od_observada, mbase)
    estado = state.construir_estado(mbase, delta)

    # 4. Gating (la presencia de incidencias fuerza el recálculo aunque ‖ΔM‖₂ ≤ ε).
    incidencias = await _leer_incidencias(redis, settings)
    optimizar = gating.debe_optimizar(estado.norma_delta, settings.EPSILON, bool(incidencias))

    # 5. Plan: itinerario base o MILP.
    if optimizar:
        max_despachos = max(1, settings.HORIZONTE_MIN // settings.HEADWAY_MIN)
        plan_engine = milp.resolver_despacho(
            ahora=ahora,
            m_hat=estado.m_hat,
            restricciones=milp.RestriccionesFlota(
                flota_total=settings.FLOTA_TOTAL,
                conductores_disponibles=settings.CONDUCTORES_DISPONIBLES,
                capacidad_bus=settings.CAPACIDAD_BUS,
                max_despachos=max_despachos,
            ),
            norma_delta=estado.norma_delta,
            incidencias=incidencias,
        )
    else:
        plan_engine = milp.itinerario_base(ahora, estado.norma_delta)

    plan_api = DispatchPlanAPI.desde_engine(plan_engine)
    payload = plan_api.model_dump(mode="json")

    # 6. Persistir siempre (el GET pull debe ver el plan fresco) pero difundir por WebSocket
    #    SOLO si la decisión cambió respecto al último plan emitido: las apps cliente reciben
    #    un empuje únicamente cuando hay algo nuevo que actuar (p.ej. al romperse el umbral ε).
    global _ultima_firma
    await redis.set(settings.KEY_PLAN_ACTUAL, json.dumps(payload))

    firma = _firma_plan(payload)
    cambio = firma != _ultima_firma
    if cambio:
        await manager.broadcast_json(payload)
        _ultima_firma = firma

    logger.info(
        "Ciclo de despacho: tipo_dia=%s eventos=%d optimizado=%s norma=%.2f cambio=%s clientes=%d",
        tipo_dia, len(eventos), plan_engine.optimizado, estado.norma_delta, cambio, manager.total,
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

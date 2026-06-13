"""
Ciclo de vida de la aplicación (FastAPI lifespan).

Arranque: abre el pool de Redis, (en Fase 2) carga Mbase en caché y arranca el scheduler del
bucle de control. Apagado: detiene el scheduler y cierra Redis de forma ordenada.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.mbase_cache import cargar_mbase
from app.core.redis_client import close_redis, init_redis
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.tabla_despacho import cargar_tabla

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL)

    redis = await init_redis()
    logger.info("Redis inicializado: %s", settings.REDIS_URL)

    # Cargar la línea base Mbase (matrices OD históricas) a memoria.
    n_mbase = await cargar_mbase(redis)
    if n_mbase == 0:
        logger.warning("Mbase no encontrada: ejecuta 'python scripts/seed_baseline.py'. "
                       "Operando con Mbase=0 (ΔM = OD observada).")
    else:
        logger.info("Mbase cargada: %d tipos de día", n_mbase)

    # Cargar la tabla de despacho precalculada (plan base pico-consciente por hora).
    n_tabla = await cargar_tabla(redis)
    if n_tabla == 0:
        logger.warning("Tabla de despacho no encontrada: el caso base usará el itinerario fijo. "
                       "Ejecuta 'python scripts/seed_baseline.py'.")
    else:
        logger.info("Tabla de despacho precalculada cargada: %d tipos de día", n_tabla)

    start_scheduler(settings)

    try:
        yield
    finally:
        stop_scheduler()
        await close_redis()
        logger.info("Apagado ordenado completo")

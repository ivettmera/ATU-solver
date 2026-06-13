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
from app.core.redis_client import close_redis, init_redis
from app.core.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging.basicConfig(level=settings.LOG_LEVEL)

    await init_redis()
    logger.info("Redis inicializado: %s", settings.REDIS_URL)

    # TODO(Fase 2): cargar Mbase (matrices OD históricas) en caché aquí.

    start_scheduler(settings)

    try:
        yield
    finally:
        stop_scheduler()
        await close_redis()
        logger.info("Apagado ordenado completo")

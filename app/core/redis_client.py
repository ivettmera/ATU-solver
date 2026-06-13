"""
Cliente Redis asíncrono (pool compartido por la app).

Redis cumple dos roles: buffer de telemetría por ventana de 5 min y caché del estado del
sistema (Mbase, incidencias activas, último plan de despacho). El pool se inicializa en el
`lifespan` y se inyecta en los endpoints vía `get_redis`.
"""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


async def init_redis() -> Redis:
    """Crea el pool global de Redis (llamado al arrancar la app)."""
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis() -> None:
    """Cierra el pool global (llamado al apagar la app)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def get_redis() -> Redis:
    """
    Dependencia FastAPI: devuelve el pool ya inicializado.

    Lanza RuntimeError si se usa antes del arranque (lifespan no ejecutado).
    """
    if _redis is None:
        raise RuntimeError("Redis no inicializado: ¿se ejecutó el lifespan de la app?")
    return _redis

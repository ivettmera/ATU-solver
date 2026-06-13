"""
Seed de la línea base (Mbase) en Redis.

Calcula Mbase offline (por tipo de día × bloque) y la persiste en Redis para que el bucle de
control la sirva en O(1). En la Entrega 1 es un stub que escribe matrices vacías con la forma
correcta del corredor; en Fase 2 generará Mbase a partir de las OD reconstruidas de datos
sintéticos.

Uso:
    python scripts/seed_baseline.py
"""

from __future__ import annotations

import asyncio
import json

from app.core.config import get_settings
from app.core.redis_client import close_redis, init_redis
from engine.demand import baseline


async def main() -> None:
    settings = get_settings()
    redis = await init_redis()

    n_bloques = (24 * 60) // settings.BLOQUE_MIN  # bloques por día
    escritas = 0
    for tipo_dia in baseline.TIPOS_DIA:
        for bloque in range(n_bloques):
            clave = baseline.clave_baseline(tipo_dia, bloque)
            matriz = baseline.matriz_vacia()  # TODO(Fase 2): Mbase real
            await redis.set(clave, json.dumps(matriz.tolist()))
            escritas += 1

    print(f"Mbase sembrada: {escritas} matrices ({len(baseline.TIPOS_DIA)} tipos × {n_bloques} bloques)")
    await close_redis()


if __name__ == "__main__":
    asyncio.run(main())

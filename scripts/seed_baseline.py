"""
Seed de la línea base (Mbase) en Redis.

Calcula Mbase offline a partir de un histórico sintético (varios días por tipo de día) y la
persiste en Redis para que el bucle de control la sirva en O(1). Al migrar a datos reales, solo
cambia la fuente de los días en `engine.demand.historico`.

Uso:
    python scripts/seed_baseline.py [--dias N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.redis_client import close_redis, init_redis  # noqa: E402
from engine.demand import baseline, historico  # noqa: E402


async def sembrar(dias_por_tipo: int) -> None:
    redis = await init_redis()

    print(f"Construyendo Mbase con {dias_por_tipo} días/tipo (puede tardar)...")
    mbase = historico.construir_mbase_sintetico(dias_por_tipo=dias_por_tipo)

    for tipo_dia, matriz in mbase.items():
        clave = baseline.clave_baseline(tipo_dia)
        await redis.set(clave, baseline.matriz_a_json(matriz))
        print(f"  [OK] {clave:20s}  viajes/día≈{matriz.sum():.0f}")

    await close_redis()
    print(f"Mbase sembrada: {len(mbase)} tipos de día.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de Mbase para ATU resolver")
    parser.add_argument("--dias", type=int, default=20, help="días sintéticos por tipo de día")
    args = parser.parse_args()
    asyncio.run(sembrar(args.dias))


if __name__ == "__main__":
    main()

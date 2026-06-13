"""
Seed de la línea base (Mbase) en Redis.

Calcula Mbase offline y la persiste en Redis para que el bucle de control la sirva en O(1).
Dos fuentes:
  - por defecto: histórico **sintético** en memoria (varios días por tipo de día);
  - `--csv DIR`: a partir de **CSV por tarjeta** (datos sintéticos de prueba o reales).
Al migrar a datos reales basta apuntar `--csv` a `data/raw/`.

Uso:
    python scripts/seed_baseline.py [--dias N]
    python scripts/seed_baseline.py --csv data/sintetico
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.redis_client import close_redis, init_redis  # noqa: E402
from engine.data_loader import cargar_eventos_dir  # noqa: E402
from engine.demand import baseline, historico  # noqa: E402


async def _persistir(mbase: dict) -> None:
    redis = await init_redis()
    for tipo_dia, matriz in mbase.items():
        clave = baseline.clave_baseline(tipo_dia)
        await redis.set(clave, baseline.matriz_a_json(matriz))
        print(f"  [OK] {clave:20s}  viajes/día≈{matriz.sum():.0f}")
    await close_redis()
    print(f"Mbase sembrada: {len(mbase)} tipos de día.")


async def sembrar_sintetico(dias_por_tipo: int) -> None:
    print(f"Construyendo Mbase con {dias_por_tipo} días/tipo (en memoria)...")
    mbase = historico.construir_mbase_sintetico(dias_por_tipo=dias_por_tipo)
    await _persistir(mbase)


async def sembrar_csv(directorio: str) -> None:
    print(f"Cargando CSV por tarjeta desde {directorio}...")
    eventos = cargar_eventos_dir(directorio)
    print(f"  {len(eventos)} eventos cargados; reconstruyendo OD por día...")
    mbase = historico.construir_mbase_desde_eventos(eventos)
    await _persistir(mbase)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de Mbase para ATU resolver")
    parser.add_argument("--dias", type=int, default=20, help="días sintéticos por tipo de día")
    parser.add_argument("--csv", type=str, default=None,
                        help="directorio con CSV por tarjeta (en vez del sintético en memoria)")
    args = parser.parse_args()

    if args.csv:
        asyncio.run(sembrar_csv(args.csv))
    else:
        asyncio.run(sembrar_sintetico(args.dias))


if __name__ == "__main__":
    main()

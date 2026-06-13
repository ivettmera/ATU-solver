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

from app.core.config import get_settings  # noqa: E402
from app.core.redis_client import close_redis, init_redis  # noqa: E402
from engine.data_loader import cargar_eventos_dir  # noqa: E402
from engine.demand import baseline, historico  # noqa: E402
from engine.optimizer import milp, precompute  # noqa: E402


def _construir_tabla(mbase_intradia: dict) -> dict:
    """Precalcula la tabla de despacho por (tipo_día, hora) con los parámetros operativos."""
    s = get_settings()
    restr = milp.RestriccionesFlota(
        flota_total=s.FLOTA_TOTAL,
        conductores_disponibles=s.CONDUCTORES_DISPONIBLES,
        capacidad_bus=s.CAPACIDAD_BUS,
        max_despachos=max(1, s.HORIZONTE_MIN // s.HEADWAY_MIN),
    )
    return precompute.construir_tabla_despacho(mbase_intradia, restr, objetivo=s.OBJETIVO_DESPACHO)


async def _persistir(mbase: dict, mbase_intradia: dict, tabla: dict) -> None:
    redis = await init_redis()
    for tipo_dia, matriz in mbase.items():
        clave = baseline.clave_baseline(tipo_dia)
        await redis.set(clave, baseline.matriz_a_json(matriz))
        print(f"  [OK] {clave:20s}  viajes/día≈{matriz.sum():.0f}")
    for tipo_dia, tensor in mbase_intradia.items():
        clave = baseline.clave_baseline_intradia(tipo_dia)
        await redis.set(clave, baseline.matriz_a_json(tensor))
        pico = int(tensor.sum(axis=(1, 2)).argmax())
        print(f"  [OK] {clave:28s}  pico hora {pico:02d}")
    await redis.set(precompute.CLAVE_TABLA, precompute.tabla_a_json(tabla))
    n_escenarios = sum(len(por_hora) for por_hora in tabla.values())
    print(f"  [OK] {precompute.CLAVE_TABLA:28s}  {n_escenarios} escenarios (tipo_día × hora)")
    await close_redis()
    print(f"Sembrado: {len(mbase)} Mbase diarias + {len(mbase_intradia)} intradía + tabla de despacho.")


async def sembrar_sintetico(dias_por_tipo: int) -> None:
    print(f"Construyendo Mbase (diaria + intradía) con {dias_por_tipo} días/tipo (en memoria)...")
    mbase = historico.construir_mbase_sintetico(dias_por_tipo=dias_por_tipo)
    mbase_intradia = historico.construir_mbase_intradia_sintetico(dias_por_tipo=dias_por_tipo)
    tabla = _construir_tabla(mbase_intradia)
    await _persistir(mbase, mbase_intradia, tabla)


async def sembrar_csv(directorio: str) -> None:
    print(f"Cargando CSV por tarjeta desde {directorio}...")
    eventos = cargar_eventos_dir(directorio)
    print(f"  {len(eventos)} eventos cargados; reconstruyendo OD (diaria + intradía) por día...")
    mbase = historico.construir_mbase_desde_eventos(eventos)
    mbase_intradia = historico.construir_mbase_intradia_desde_eventos(eventos)
    tabla = _construir_tabla(mbase_intradia)
    await _persistir(mbase, mbase_intradia, tabla)


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

"""
Generador de CSV sintéticos por tarjeta.

Escribe un CSV por día en `data/sintetico/`, con el **mismo formato** que tendrán los datos
reales por tarjeta: una fila por ingreso al torniquete con `tarjeta_id`, `timestamp_entrada`
y `estacion_origen`. Sirve para ejercitar todo el pipeline de datos reales (cargador → trip
chaining → Mbase) mientras llegan los CSV verdaderos.

El nivel de demanda de cada día se escala según su tipo (laboral/sábado/domingo/feriado), igual
que en `engine.demand.historico`.

Uso:
    python scripts/generar_csv_sintetico.py [--dias N] [--inicio AAAA-MM-DD] [--salida DIR]
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.demand import baseline, historico  # noqa: E402
from engine.trip_chaining import synthetic  # noqa: E402

CAMPOS = ["tarjeta_id", "timestamp_entrada", "estacion_origen"]


def generar(dias: int, inicio: date, salida: Path) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    total_eventos = 0

    for i in range(dias):
        dia = inicio + timedelta(days=i)
        tipo = baseline.clasificar_dia(dia)
        n_usuarios = historico.NIVEL_DEMANDA[tipo]
        base = datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc)

        eventos, _ = synthetic.generar_dia(
            n_usuarios=n_usuarios, semilla=1000 + i, fecha=base
        )

        ruta = salida / f"validaciones_{dia.isoformat()}.csv"
        with ruta.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS)
            w.writeheader()
            for ev in eventos:
                w.writerow({
                    "tarjeta_id": ev.tarjeta_id,
                    "timestamp_entrada": ev.timestamp.isoformat(),
                    "estacion_origen": ev.estacion_origen,
                })
        total_eventos += len(eventos)
        print(f"  [OK] {ruta.name:32s} {tipo:8s} {len(eventos):6d} eventos")

    print(f"Generados {dias} días en {salida} ({total_eventos} eventos en total).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de CSV sintéticos por tarjeta")
    parser.add_argument("--dias", type=int, default=14, help="número de días a generar")
    parser.add_argument("--inicio", type=date.fromisoformat, default=date(2026, 6, 1),
                        help="fecha de inicio (AAAA-MM-DD)")
    parser.add_argument("--salida", type=Path,
                        default=Path(__file__).resolve().parent.parent / "data" / "sintetico")
    args = parser.parse_args()
    generar(args.dias, args.inicio, args.salida)


if __name__ == "__main__":
    main()

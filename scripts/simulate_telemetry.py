"""
Simulador de telemetría de torniquetes.

Genera lotes de eventos de ingreso sintéticos y los postea a /api/v1/telemetry/ingress en un
bucle, imitando la red de torniquetes que envía datos cada ~5 min. Útil para probar la API
desde /docs y ver el WebSocket /dispatch/stream empujando planes.

Uso:
    python scripts/simulate_telemetry.py [--url URL] [--intervalo SEG] [--eventos N] [--una-vez]
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.trip_chaining import synthetic  # noqa: E402


def generar_lote(n_usuarios: int, semilla: int) -> dict:
    """
    Construye un TelemetryPayload con cadenas de viajes realistas.

    Usa el generador sintético (mismas reglas que validan el trip chaining), de modo que la
    OD reconstruida por el scheduler tenga estructura real y no ruido uniforme.
    """
    eventos_dom, _ = synthetic.generar_dia(n_usuarios=n_usuarios, semilla=semilla)
    eventos = [
        {
            "tarjeta_id": ev.tarjeta_id,
            "timestamp_entrada": ev.timestamp.isoformat(),
            "estacion_origen": ev.estacion_origen,
        }
        for ev in eventos_dom
    ]
    return {"timestamp_envio": datetime.now(timezone.utc).isoformat(), "eventos": eventos}


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de telemetría ATU resolver")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--intervalo", type=float, default=10.0, help="segundos entre lotes")
    parser.add_argument("--usuarios", type=int, default=400, help="tarjetas por lote")
    parser.add_argument("--una-vez", action="store_true", help="enviar un solo lote y salir")
    args = parser.parse_args()

    endpoint = f"{args.url}/api/v1/telemetry/ingress"
    semilla = 0
    with httpx.Client(timeout=10.0) as client:
        while True:
            lote = generar_lote(args.usuarios, semilla)
            resp = client.post(endpoint, json=lote)
            resp.raise_for_status()
            n = len(lote["eventos"])
            print(f"[{datetime.now():%H:%M:%S}] enviados {n} eventos → {resp.json()}")
            semilla += 1
            if args.una_vez:
                break
            time.sleep(args.intervalo)


if __name__ == "__main__":
    main()

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
import random
import time
from datetime import datetime, timezone

import httpx

from engine.network import topology


def generar_lote(n: int) -> dict:
    """Construye un TelemetryPayload con `n` eventos aleatorios."""
    ahora = datetime.now(timezone.utc)
    eventos = [
        {
            "tarjeta_id": f"TARJ-{random.randint(0, 9999):04d}",
            "timestamp_entrada": ahora.isoformat(),
            "estacion_origen": random.choice(topology.ESTACIONES),
        }
        for _ in range(n)
    ]
    return {"timestamp_envio": ahora.isoformat(), "eventos": eventos}


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador de telemetría MetroSmart")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--intervalo", type=float, default=10.0, help="segundos entre lotes")
    parser.add_argument("--eventos", type=int, default=200, help="eventos por lote")
    parser.add_argument("--una-vez", action="store_true", help="enviar un solo lote y salir")
    args = parser.parse_args()

    endpoint = f"{args.url}/api/v1/telemetry/ingress"
    with httpx.Client(timeout=10.0) as client:
        while True:
            lote = generar_lote(args.eventos)
            resp = client.post(endpoint, json=lote)
            resp.raise_for_status()
            print(f"[{datetime.now():%H:%M:%S}] enviados {args.eventos} eventos → {resp.json()}")
            if args.una_vez:
                break
            time.sleep(args.intervalo)


if __name__ == "__main__":
    main()

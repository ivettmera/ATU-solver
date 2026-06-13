"""
Gestor de conexiones WebSocket.

Mantiene el conjunto de apps cliente conectadas a `/dispatch/stream` y permite empujar
(broadcast) el plan de despacho a todas apenas el motor termina de calcular uno nuevo
(cuando el gating rompe el umbral ε o hay una incidencia).
"""

from __future__ import annotations

import asyncio

from fastapi import WebSocket


class ConnectionManager:
    """Registro de WebSockets activos con difusión tolerante a fallos."""

    def __init__(self) -> None:
        self._activas: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._activas.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._activas.discard(websocket)

    @property
    def total(self) -> int:
        return len(self._activas)

    async def broadcast_json(self, payload: dict) -> None:
        """
        Envía `payload` (JSON) a todas las conexiones. Las que fallan se descartan
        para no bloquear la difusión al resto.
        """
        async with self._lock:
            destinos = list(self._activas)

        caidas: list[WebSocket] = []
        for ws in destinos:
            try:
                await ws.send_json(payload)
            except Exception:
                caidas.append(ws)

        if caidas:
            async with self._lock:
                for ws in caidas:
                    self._activas.discard(ws)


# Singleton compartido por endpoints y scheduler.
manager = ConnectionManager()

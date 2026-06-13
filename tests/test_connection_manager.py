"""Pruebas del ConnectionManager de WebSockets (asyncio puro, sin servidor)."""

from unittest.mock import AsyncMock

from app.ws.connection_manager import ConnectionManager


def _fake_ws() -> AsyncMock:
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


async def test_connect_y_broadcast():
    mgr = ConnectionManager()
    ws = _fake_ws()
    await mgr.connect(ws)
    assert mgr.total == 1

    await mgr.broadcast_json({"hola": "mundo"})
    ws.send_json.assert_awaited_once_with({"hola": "mundo"})


async def test_disconnect():
    mgr = ConnectionManager()
    ws = _fake_ws()
    await mgr.connect(ws)
    await mgr.disconnect(ws)
    assert mgr.total == 0


async def test_broadcast_descarta_conexiones_caidas():
    mgr = ConnectionManager()
    ok, caida = _fake_ws(), _fake_ws()
    caida.send_json.side_effect = RuntimeError("conexión rota")
    await mgr.connect(ok)
    await mgr.connect(caida)

    await mgr.broadcast_json({"x": 1})

    # La conexión que falló se purga; la sana permanece.
    assert mgr.total == 1
    ok.send_json.assert_awaited_once()

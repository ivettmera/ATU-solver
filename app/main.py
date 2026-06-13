"""
Punto de entrada de la API MetroSmart.

Encapsula el procesamiento matemático (trip chaining, estimación residual y MILP) detrás de
endpoints REST + WebSocket documentados con Pydantic. El frontend y las apps móviles son
externos: se comunican estrictamente vía JSON y WebSockets, sin conocer la matemática interna.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.lifespan import lifespan
from engine.network import topology


def create_app() -> FastAPI:
    app = FastAPI(
        title="ATU resolver — API de despacho inteligente",
        description=(
            "Despacho de buses en tiempo real para el Metropolitano de Lima. "
            "Reconstruye la matriz Origen-Destino por trip chaining, estima la demanda con "
            "Mbase + ΔM(t) (Kalman) y optimiza el despacho con MILP bajo un mecanismo de guarda."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS abierto para que el equipo móvil/frontend consuma los contratos en desarrollo.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["Infra"])
    async def health() -> dict:
        return {"estado": "ok", "estaciones": topology.N_ESTACIONES}

    return app


app = create_app()

"""Agregador de routers de la versión v1 de la API."""

from fastapi import APIRouter

from app.api.v1 import dispatch, incidents, red, telemetry

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(telemetry.router)
api_router.include_router(incidents.router)
api_router.include_router(dispatch.router)
api_router.include_router(red.router)

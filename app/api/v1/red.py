"""
Información de la red — /api/v1/red.

Endpoints de solo lectura que describen la topología y los parámetros operativos. Sirven para
poblar interfaces (dashboard, apps cliente): listas de estaciones/terminales, servicios y la
configuración relevante (umbral de gating, flota, capacidad).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from engine.network import topology

router = APIRouter(prefix="/red", tags=["Red"])


@router.get("/estaciones")
def estaciones() -> dict:
    return {
        "estaciones": topology.ESTACIONES,
        "terminales": topology.TERMINALES,
        "total": topology.N_ESTACIONES,
    }


@router.get("/servicios")
def servicios() -> list[dict]:
    return [
        {"codigo": s.codigo, "nombre": s.nombre, "n_paradas": len(s.paradas)}
        for s in topology.SERVICIOS
    ]


@router.get("/config")
def config(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "epsilon": settings.EPSILON,
        "flota_total": settings.FLOTA_TOTAL,
        "conductores_disponibles": settings.CONDUCTORES_DISPONIBLES,
        "capacidad_bus": settings.CAPACIDAD_BUS,
        "intervalo_opt_seg": settings.INTERVALO_OPT_SEG,
    }

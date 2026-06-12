"""
Router FastAPI del módulo de IA — MetroSmart (RF05).
Se registra en el backend principal con prefix="/ia".

Endpoints:
  POST /ia/prediccion          → demanda predicha por estación y rango de fechas
  POST /ia/cuellos-botella     → estaciones con sobrecarga en el período
  GET  /ia/estaciones          → lista de estaciones disponibles
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import APIRouter, HTTPException
from predict import predecir
from bottleneck import resumen_cuellos
from data_generation import ESTACIONES
from .schemas import (
    PrediccionRequest, PrediccionResponse, PrediccionDia,
    CuellosRequest, CuellosResponse, CuelloBotella,
)

router = APIRouter(prefix="/ia", tags=["IA - Predicción de Demanda"])


@router.get("/estaciones")
def listar_estaciones() -> list[str]:
    return ESTACIONES


@router.post("/prediccion", response_model=PrediccionResponse)
def predecir_demanda(body: PrediccionRequest):
    if body.estacion not in ESTACIONES:
        raise HTTPException(status_code=404, detail=f"Estación '{body.estacion}' no encontrada.")
    try:
        df = predecir(
            estacion=body.estacion,
            fecha_inicio=body.fecha_inicio,
            dias=body.dias,
            disponibilidad_chofer=body.disponibilidad_chofer,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Modelo no disponible. Ejecute el pipeline de entrenamiento primero.",
        )

    predicciones = [
        PrediccionDia(
            fecha=row["ds"].date(),
            prediccion=max(int(row["yhat"]), 0),
            intervalo_inferior=max(int(row["yhat_lower"]), 0),
            intervalo_superior=max(int(row["yhat_upper"]), 0),
        )
        for _, row in df.iterrows()
    ]
    return PrediccionResponse(estacion=body.estacion, predicciones=predicciones)


@router.post("/cuellos-botella", response_model=CuellosResponse)
def detectar_cuellos(body: CuellosRequest):
    cuellos_raw = resumen_cuellos(
        fecha_inicio=body.fecha_inicio,
        dias=body.dias,
        disponibilidad_chofer=body.disponibilidad_chofer,
        umbral_pct=body.umbral_pct,
    )
    cuellos = [CuelloBotella(**c) for c in cuellos_raw]
    return CuellosResponse(total_cuellos=len(cuellos), cuellos=cuellos)

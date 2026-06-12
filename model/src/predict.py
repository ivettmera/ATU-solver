"""
Módulo de inferencia: carga modelos Prophet entrenados y genera predicciones.
Usado directamente por el router FastAPI.
"""

import os
import pickle
import pandas as pd
from datetime import date, timedelta
from typing import Optional

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

_cache_modelos: dict = {}


def _nombre_archivo(estacion: str) -> str:
    return estacion.lower().replace(" ", "_").replace("á","a").replace("é","e") \
                           .replace("í","i").replace("ó","o").replace("ú","u")


def cargar_modelo(estacion: str):
    """Carga un modelo desde disco con caché en memoria."""
    if estacion not in _cache_modelos:
        ruta = os.path.join(MODELS_DIR, f"prophet_{_nombre_archivo(estacion)}.pkl")
        if not os.path.exists(ruta):
            raise FileNotFoundError(f"Modelo no encontrado para estación: {estacion}")
        with open(ruta, "rb") as f:
            _cache_modelos[estacion] = pickle.load(f)
    return _cache_modelos[estacion]


def predecir(
    estacion: str,
    fecha_inicio: date,
    dias: int = 7,
    disponibilidad_chofer: float = 0.95,
) -> pd.DataFrame:
    """
    Genera predicción de validaciones para `dias` días desde `fecha_inicio`.

    Returns:
        DataFrame con columnas: ds, yhat, yhat_lower, yhat_upper
    """
    modelo = cargar_modelo(estacion)
    fechas = [fecha_inicio + timedelta(days=i) for i in range(dias)]
    futuro = pd.DataFrame({
        "ds": pd.to_datetime(fechas),
        "disponibilidad_chofer": disponibilidad_chofer,
    })
    forecast = modelo.predict(futuro)
    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()


def predecir_hoy(estacion: str, disponibilidad_chofer: float = 0.95) -> dict:
    """Predicción para el día actual (uso rápido desde la API)."""
    df = predecir(estacion, date.today(), dias=1, disponibilidad_chofer=disponibilidad_chofer)
    row = df.iloc[0]
    return {
        "estacion": estacion,
        "fecha": str(row["ds"].date()),
        "prediccion": max(int(row["yhat"]), 0),
        "intervalo_inferior": max(int(row["yhat_lower"]), 0),
        "intervalo_superior": max(int(row["yhat_upper"]), 0),
    }

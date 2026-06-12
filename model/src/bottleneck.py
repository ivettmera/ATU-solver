"""
Detección de cuellos de botella en el sistema BRT de Lima.
Un cuello de botella ocurre cuando la demanda predicha supera la capacidad operativa
de la estación (umbral configurable en función de la flota disponible).
"""

import pandas as pd
from datetime import date
from typing import Optional

from data_generation import ESTACIONES
from predict import predecir

CAPACIDAD_BASE = 5000  # validaciones/día sin restricción de flota


def calcular_carga(
    prediccion: int,
    capacidad: int = CAPACIDAD_BASE,
) -> float:
    """Retorna el porcentaje de carga respecto a la capacidad."""
    return round(prediccion / capacidad * 100, 2)


def detectar_cuellos_botella(
    fecha_inicio: date,
    dias: int = 7,
    disponibilidad_chofer: float = 0.90,
    umbral_pct: float = 85.0,
) -> pd.DataFrame:
    """
    Evalúa todas las estaciones en el rango de fechas y marca las que superan el umbral.

    Returns:
        DataFrame con columnas: estacion, fecha, prediccion, carga_pct, cuello_botella
    """
    filas = []
    for estacion in ESTACIONES:
        try:
            df = predecir(estacion, fecha_inicio, dias, disponibilidad_chofer)
        except FileNotFoundError:
            continue
        for _, row in df.iterrows():
            pred = max(int(row["yhat"]), 0)
            carga = calcular_carga(pred)
            filas.append({
                "estacion": estacion,
                "fecha": row["ds"].date(),
                "prediccion": pred,
                "carga_pct": carga,
                "cuello_botella": carga >= umbral_pct,
            })

    return pd.DataFrame(filas)


def resumen_cuellos(
    fecha_inicio: date,
    dias: int = 7,
    disponibilidad_chofer: float = 0.90,
    umbral_pct: float = 85.0,
) -> list[dict]:
    """Versión simplificada para consumo directo desde la API."""
    df = detectar_cuellos_botella(fecha_inicio, dias, disponibilidad_chofer, umbral_pct)
    cuellos = df[df["cuello_botella"]].copy()
    return cuellos.to_dict(orient="records")

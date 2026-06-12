"""
Pipeline de entrenamiento de modelos Prophet por estación.
Escala a las 28 estaciones del sistema BRT de Lima y serializa cada modelo en models/.
"""

import os
import pickle
import pandas as pd
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
from typing import Optional

from data_generation import ESTACIONES, generar_todas_estaciones

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "models")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")


def _nombre_archivo(estacion: str) -> str:
    return estacion.lower().replace(" ", "_").replace("á","a").replace("é","e") \
                           .replace("í","i").replace("ó","o").replace("ú","u")


def entrenar_estacion(
    df_estacion: pd.DataFrame,
    estacion: str,
    guardar: bool = True,
) -> tuple[Prophet, dict]:
    """
    Entrena un modelo Prophet para una estación y devuelve (modelo, métricas).

    Prophet configuration:
    - Tendencia lineal por tramos
    - Estacionalidad semanal y anual (series de Fourier)
    - Regresor externo: disponibilidad_chofer
    - Incertidumbre con MAP (interval_width=0.95)
    """
    df = df_estacion[["ds", "y", "disponibilidad_chofer"]].copy()
    corte = int(len(df) * 0.8)
    train, test = df.iloc[:corte], df.iloc[corte:]

    modelo = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.95,
        changepoint_prior_scale=0.05,
    )
    modelo.add_regressor("disponibilidad_chofer")
    modelo.fit(train)

    forecast = modelo.predict(test[["ds", "disponibilidad_chofer"]])
    mae = mean_absolute_error(test["y"], forecast["yhat"])
    mse = mean_squared_error(test["y"], forecast["yhat"])
    metricas = {"estacion": estacion, "MAE": round(mae, 2), "MSE": round(mse, 2)}

    if guardar:
        os.makedirs(MODELS_DIR, exist_ok=True)
        ruta = os.path.join(MODELS_DIR, f"prophet_{_nombre_archivo(estacion)}.pkl")
        with open(ruta, "wb") as f:
            pickle.dump(modelo, f)

    return modelo, metricas


def entrenar_todas(df_total: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Entrena modelos para las 28 estaciones.
    Si df_total es None carga data/processed/validaciones_todas_estaciones.csv.
    Guarda data/processed/metricas_28_estaciones.csv y retorna el DataFrame de métricas.
    """
    if df_total is None:
        ruta_csv = os.path.join(DATA_DIR, "processed", "validaciones_todas_estaciones.csv")
        df_total = pd.read_csv(ruta_csv, parse_dates=["ds"])

    metricas = []
    for estacion in ESTACIONES:
        df_est = df_total[df_total["estacion"] == estacion].copy()
        if df_est.empty:
            continue
        _, m = entrenar_estacion(df_est, estacion)
        metricas.append(m)
        print(f"[OK] {estacion:30s}  MAE={m['MAE']:.1f}  MSE={m['MSE']:.1f}")

    df_metricas = pd.DataFrame(metricas)
    ruta_metricas = os.path.join(DATA_DIR, "processed", "metricas_28_estaciones.csv")
    os.makedirs(os.path.dirname(ruta_metricas), exist_ok=True)
    df_metricas.to_csv(ruta_metricas, index=False)
    return df_metricas


if __name__ == "__main__":
    print("Generando datos sintéticos...")
    df = generar_todas_estaciones(
        ruta_salida=os.path.join(DATA_DIR, "processed", "validaciones_todas_estaciones.csv")
    )
    print("Entrenando modelos...")
    entrenar_todas(df)
    print("Listo.")

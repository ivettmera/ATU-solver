"""
Generación de datos sintéticos de alta fidelidad para el sistema BRT de Lima.
Basado en patrones reales del portal Protarjeta (ATU-Protransporte): 28 estaciones,
perfiles horarios por tipo de día, impacto de feriados y disponibilidad de choferes.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Optional

# ── Configuración del sistema ────────────────────────────────────────────────

ESTACIONES = [
    "Naranjal", "Independencia", "Izaguirre", "Habich", "UNI",
    "Caqueta", "Honorio Delgado", "Peru", "Domingo Orue",
    "Nicolas Arriola", "Mexico", "Canadá", "Aviacion",
    "Angamos", "Benavides", "Surco", "Higuereta", "Primavera",
    "Javier Prado", "Paseo de la Republica",
    "28 de Julio", "Estadio Nacional", "Grau", "Colonial",
    "Argentina", "Plaza de Armas", "Tacna", "Matellini"
]

VALIDACIONES_BASE = {
    "Javier Prado": 8200,
    "Angamos": 7500,
    "Naranjal": 7000,
    "default": 4500,
}

FERIADOS_PERU = [
    "01-01", "04-17", "04-18", "05-01", "06-07", "06-29",
    "07-28", "07-29", "08-30", "10-08", "11-01", "12-08", "12-25",
]


def _es_feriado(fecha: date) -> bool:
    return fecha.strftime("%m-%d") in FERIADOS_PERU


def _perfil_horario(tipo_dia: str) -> np.ndarray:
    """Distribución proporcional de validaciones en 24 horas según tipo de día."""
    if tipo_dia == "laboral":
        perfil = np.zeros(24)
        perfil[6:9] = [0.08, 0.12, 0.10]   # pico mañana
        perfil[12:14] = [0.07, 0.06]         # mediodía
        perfil[17:20] = [0.10, 0.13, 0.09]  # pico tarde
        perfil[9:12] = 0.04
        perfil[14:17] = 0.04
        perfil[20:23] = 0.03
    else:
        perfil = np.zeros(24)
        perfil[9:13] = 0.09
        perfil[14:18] = 0.08
        perfil[18:21] = 0.05
    perfil /= perfil.sum()
    return perfil


def generar_datos_estacion(
    estacion: str,
    fecha_inicio: date = date(2023, 1, 1),
    fecha_fin: date = date(2023, 12, 31),
    semilla: int = 42,
) -> pd.DataFrame:
    """
    Genera serie temporal diaria de validaciones para una estación.

    Returns:
        DataFrame con columnas: ds, y, estacion, tipo_dia, es_feriado, disponibilidad_chofer
    """
    rng = np.random.default_rng(semilla)
    base = VALIDACIONES_BASE.get(estacion, VALIDACIONES_BASE["default"])
    fechas = pd.date_range(fecha_inicio, fecha_fin, freq="D")
    registros = []

    for fecha in fechas:
        es_feriado = _es_feriado(fecha.date())
        tipo_dia = "feriado" if es_feriado else ("fin_semana" if fecha.weekday() >= 5 else "laboral")
        factor_dia = {"laboral": 1.0, "fin_semana": 0.65, "feriado": 0.40}[tipo_dia]
        disponibilidad = rng.uniform(0.80, 1.0)
        ruido = rng.normal(1.0, 0.05)
        validaciones = int(base * factor_dia * disponibilidad * ruido)
        registros.append({
            "ds": fecha,
            "y": max(validaciones, 0),
            "estacion": estacion,
            "tipo_dia": tipo_dia,
            "es_feriado": es_feriado,
            "disponibilidad_chofer": round(disponibilidad, 4),
        })

    return pd.DataFrame(registros)


def generar_todas_estaciones(
    fecha_inicio: date = date(2023, 1, 1),
    fecha_fin: date = date(2023, 12, 31),
    ruta_salida: Optional[str] = None,
) -> pd.DataFrame:
    """Genera datos para las 28 estaciones y opcionalmente los guarda en CSV."""
    dfs = [generar_datos_estacion(est, fecha_inicio, fecha_fin, semilla=i)
           for i, est in enumerate(ESTACIONES)]
    df_total = pd.concat(dfs, ignore_index=True)

    if ruta_salida:
        df_total.to_csv(ruta_salida, index=False)

    return df_total

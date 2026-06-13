"""
Configuración de la aplicación (pydantic-settings).

Lee de variables de entorno y/o de un archivo `.env`. Es la fuente única de los parámetros
operativos: conexión a Redis, umbral de gating ε, cadencia de optimización y recursos de flota.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Gating
    EPSILON: float = 150.0

    # Optimización / ventanas
    INTERVALO_OPT_SEG: int = 300   # cadencia del job de despacho (5 min)
    HORIZONTE_MIN: int = 60        # horizonte deslizante del MILP
    BLOQUE_MIN: int = 5            # granularidad temporal de la ventana
    HEADWAY_MIN: int = 3           # intervalo mínimo entre salidas de un servicio
    VENTANA_TELEMETRIA_MIN: int = 120  # ventana móvil de telemetría = escala de comparación

    # Incidencias
    INCIDENCIA_TTL_SEG: int = 7200     # auto-resolución si no se refresca (2 h)

    # Flota / recursos finitos
    FLOTA_TOTAL: int = 120
    CONDUCTORES_DISPONIBLES: int = 140
    CAPACIDAD_BUS: int = 160

    # App
    LOG_LEVEL: str = "INFO"

    # Claves de Redis (namespacing)
    KEY_PLAN_ACTUAL: str = "dispatch:plan_actual"
    PREFIX_INCIDENCIA: str = "incidents:activa"
    PREFIX_TELEMETRIA: str = "telemetry:ventana"


@lru_cache
def get_settings() -> Settings:
    """Settings cacheado (una sola lectura del entorno por proceso)."""
    return Settings()

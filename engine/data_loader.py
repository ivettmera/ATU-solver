"""
Cargador de validaciones por tarjeta desde CSV.

Convierte archivos CSV (uno o un directorio) en `EventoViaje` para alimentar el trip chaining.
Está pensado tanto para los datos sintéticos de prueba como para los datos reales: por eso
admite **mapeo de columnas** (si los encabezados difieren) y **resolución de nombres de
estación** contra `topology` (tolerante a tildes y mayúsculas, con alias explícitos).

Formato canónico de columnas: `tarjeta_id`, `timestamp_entrada`, `estacion_origen`.
"""

from __future__ import annotations

import csv
import glob
import os
import unicodedata
from datetime import datetime

from engine.network import topology
from engine.trip_chaining.chaining import EventoViaje

CAMPOS_CANONICOS = ("tarjeta_id", "timestamp_entrada", "estacion_origen")


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados (para casar nombres de estación)."""
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sin_tildes.lower().split())


# Lookup normalizado → nombre oficial de la estación en la topología.
_NORM_A_ESTACION: dict[str, str] = {_normalizar(e): e for e in topology.ESTACIONES}


def resolver_estacion(nombre: str, alias: dict[str, str] | None = None) -> str:
    """
    Resuelve un nombre de estación al nombre oficial de `topology`.

    Orden: coincidencia exacta → alias explícito → coincidencia normalizada (sin tildes/caso).
    Lanza KeyError si no se puede mapear (mejor fallar que asignar mal una fila).
    """
    if topology.es_estacion_valida(nombre):
        return nombre
    if alias and nombre in alias:
        return alias[nombre]
    norm = _normalizar(nombre)
    if norm in _NORM_A_ESTACION:
        return _NORM_A_ESTACION[norm]
    if alias:
        for origen, destino in alias.items():
            if _normalizar(origen) == norm:
                return destino
    raise KeyError(f"Estación no mapeable a la topología: '{nombre}'")


def cargar_eventos_csv(
    ruta: str,
    mapeo_columnas: dict[str, str] | None = None,
    alias_estaciones: dict[str, str] | None = None,
) -> list[EventoViaje]:
    """
    Carga los eventos de un archivo CSV.

    Args:
        ruta: ruta al CSV.
        mapeo_columnas: dict {nombre_canonico: nombre_en_csv} si los encabezados difieren.
        alias_estaciones: dict {nombre_en_csv: nombre_oficial} para casos que la normalización
            no resuelve.

    Returns:
        Lista de EventoViaje. Las filas con estación no mapeable se omiten (no abortan la carga).
    """
    cols = {c: c for c in CAMPOS_CANONICOS}
    if mapeo_columnas:
        cols.update(mapeo_columnas)

    eventos: list[EventoViaje] = []
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            try:
                estacion = resolver_estacion(fila[cols["estacion_origen"]], alias_estaciones)
            except KeyError:
                continue
            eventos.append(
                EventoViaje(
                    tarjeta_id=fila[cols["tarjeta_id"]],
                    timestamp=datetime.fromisoformat(fila[cols["timestamp_entrada"]]),
                    estacion_origen=estacion,
                )
            )
    return eventos


def cargar_eventos_dir(
    directorio: str,
    mapeo_columnas: dict[str, str] | None = None,
    alias_estaciones: dict[str, str] | None = None,
) -> list[EventoViaje]:
    """Carga y concatena los eventos de todos los CSV de un directorio."""
    eventos: list[EventoViaje] = []
    for ruta in sorted(glob.glob(os.path.join(directorio, "*.csv"))):
        eventos.extend(cargar_eventos_csv(ruta, mapeo_columnas, alias_estaciones))
    return eventos

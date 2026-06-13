"""Pruebas del cargador de CSV por tarjeta y construcción de Mbase desde eventos (Fase 6)."""

import csv

import numpy as np

from engine.data_loader import (
    cargar_eventos_csv,
    cargar_eventos_dir,
    resolver_estacion,
)
from engine.demand import historico
from engine.network import topology
from engine.trip_chaining import synthetic
from engine.trip_chaining.chaining import reconstruir_od

I = topology.INDICE_ESTACION


def _escribir_csv(ruta, filas, cabecera=("tarjeta_id", "timestamp_entrada", "estacion_origen")):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        w.writerows(filas)


# ── Resolución de nombres de estación ────────────────────────────────────────────────
def test_resuelve_nombre_exacto():
    assert resolver_estacion("Estación Central") == "Estación Central"


def test_resuelve_sin_tildes_y_mayusculas():
    # Como vienen en los reportes reales: "Uni", "Pacifico", "Tomas Valle".
    assert resolver_estacion("Uni") == "UNI"
    assert resolver_estacion("Pacifico") == "Pacífico"
    assert resolver_estacion("TOMAS VALLE") == "Tomás Valle"


def test_resuelve_con_alias_explicito():
    alias = {"2 de Mayo": "Dos de Mayo"}
    assert resolver_estacion("2 de Mayo", alias=alias) == "Dos de Mayo"


# ── Carga de CSV ────────────────────────────────────────────────────────────────────────
def test_cargar_csv_basico(tmp_path):
    ruta = tmp_path / "dia.csv"
    _escribir_csv(ruta, [
        ("T-1", "2026-06-15T08:00:00", "UNI"),
        ("T-1", "2026-06-15T18:00:00", "Caquetá"),
    ])
    eventos = cargar_eventos_csv(str(ruta))
    assert len(eventos) == 2
    assert eventos[0].tarjeta_id == "T-1"
    assert eventos[0].estacion_origen == "UNI"


def test_cargar_csv_con_mapeo_de_columnas(tmp_path):
    ruta = tmp_path / "dia.csv"
    _escribir_csv(
        ruta,
        [("0001", "2026-06-15T08:00:00", "Pacifico")],
        cabecera=("card", "hora", "estacion"),
    )
    eventos = cargar_eventos_csv(str(ruta), mapeo_columnas={
        "tarjeta_id": "card", "timestamp_entrada": "hora", "estacion_origen": "estacion",
    })
    assert len(eventos) == 1
    assert eventos[0].estacion_origen == "Pacífico"  # normalizado a la topología


def test_filas_con_estacion_no_mapeable_se_omiten(tmp_path):
    ruta = tmp_path / "dia.csv"
    _escribir_csv(ruta, [
        ("T-1", "2026-06-15T08:00:00", "UNI"),
        ("T-2", "2026-06-15T09:00:00", "Estación Fantasma"),
    ])
    eventos = cargar_eventos_csv(str(ruta))
    assert len(eventos) == 1


# ── Pipeline CSV → OD (equivale al de datos reales) ──────────────────────────────────────
def test_csv_reconstruye_la_od_ground_truth(tmp_path):
    # Genera un día con cierre garantizado, lo vuelca a CSV, lo recarga y reconstruye la OD.
    eventos, od_real = synthetic.generar_dia(n_usuarios=200, semilla=3, prob_cierre=1.0)
    ruta = tmp_path / "validaciones.csv"
    _escribir_csv(ruta, [
        (e.tarjeta_id, e.timestamp.isoformat(), e.estacion_origen) for e in eventos
    ])
    recargados = cargar_eventos_csv(str(ruta))
    assert np.array_equal(reconstruir_od(recargados), od_real)


def test_construir_mbase_desde_eventos_agrupa_por_tipo_de_dia():
    # Dos días: 2026-06-15 (lunes, laboral) y 2026-06-21 (domingo).
    from datetime import datetime, timezone

    lun = datetime(2026, 6, 15, tzinfo=timezone.utc)
    dom = datetime(2026, 6, 21, tzinfo=timezone.utc)
    ev_lun, _ = synthetic.generar_dia(n_usuarios=120, semilla=1, fecha=lun)
    ev_dom, _ = synthetic.generar_dia(n_usuarios=120, semilla=2, fecha=dom)

    mbase = historico.construir_mbase_desde_eventos(ev_lun + ev_dom)
    assert "laboral" in mbase and "domingo" in mbase
    # Tipos sin datos no aparecen.
    assert "feriado" not in mbase
    assert mbase["laboral"].shape == (topology.N_ESTACIONES, topology.N_ESTACIONES)

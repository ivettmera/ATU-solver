"""Pruebas de la Fase 2: Mbase (clasificación + promedio) y Filtro de Kalman."""

from datetime import date, datetime, timezone

import numpy as np

from engine.demand import baseline, historico, state
from engine.demand.residual import KalmanResidualEstimator
from engine.network import topology

N = topology.N_ESTACIONES


# ── Clasificación de día ──────────────────────────────────────────────────────────────
def test_clasificar_feriado_tiene_prioridad_sobre_dia_semana():
    # 28 de julio (martes) y 1 de enero (jueves) son feriados pese a ser días de semana.
    assert baseline.clasificar_dia(date(2026, 7, 28)) == "feriado"
    assert baseline.clasificar_dia(date(2026, 1, 1)) == "feriado"


def test_clasificar_laboral_sabado_domingo():
    assert baseline.clasificar_dia(date(2026, 6, 15)) == "laboral"   # lunes
    assert baseline.clasificar_dia(date(2026, 6, 20)) == "sabado"    # sábado
    assert baseline.clasificar_dia(date(2026, 6, 21)) == "domingo"   # domingo


# ── Promedio y serialización de Mbase ──────────────────────────────────────────────────
def test_build_baseline_promedia_por_tipo():
    a = np.ones((N, N))
    b = np.full((N, N), 3.0)
    mbase = baseline.build_baseline({"laboral": [a, b], "feriado": []})
    # Promedio de 1 y 3 = 2; el tipo sin observaciones se omite.
    assert np.allclose(mbase["laboral"], 2.0)
    assert "feriado" not in mbase


def test_serializacion_matriz_roundtrip():
    m = np.arange(N * N, dtype=float).reshape(N, N)
    recuperada = baseline.matriz_desde_json(baseline.matriz_a_json(m))
    assert np.array_equal(m, recuperada)


def test_construir_mbase_sintetico_estructura_y_niveles():
    mbase = historico.construir_mbase_sintetico(dias_por_tipo=2, semilla=0)
    assert set(mbase) == set(baseline.TIPOS_DIA)
    for matriz in mbase.values():
        assert matriz.shape == (N, N)
    # Día laboral tiene más demanda que un feriado.
    assert mbase["laboral"].sum() > mbase["feriado"].sum()


# ── Filtro de Kalman ───────────────────────────────────────────────────────────────────
def test_kalman_primera_medicion_es_el_residuo_crudo():
    est = KalmanResidualEstimator()
    obs = np.full((N, N), 5.0)
    mbase = np.full((N, N), 2.0)
    delta = est.estimate(obs, mbase)
    assert np.allclose(delta, 3.0)  # 5 - 2, sin filtrar aún


def test_kalman_converge_a_residuo_constante():
    est = KalmanResidualEstimator(q=1.0, r=10.0)
    obs = np.full((N, N), 12.0)
    mbase = np.full((N, N), 2.0)  # residuo verdadero = 10
    delta = None
    for _ in range(50):
        delta = est.estimate(obs, mbase)
    assert np.allclose(delta, 10.0, atol=0.5)


def test_kalman_suaviza_un_pico():
    # Tras estabilizar en 0, un pico aislado se atenúa respecto a la medición cruda.
    est = KalmanResidualEstimator(q=0.5, r=20.0)
    mbase = np.zeros((N, N))
    for _ in range(20):
        est.estimate(mbase, mbase)  # residuo 0
    pico = np.full((N, N), 100.0)
    delta = est.estimate(pico, mbase)
    assert np.all(delta < 100.0)  # suavizado: no salta al valor completo
    assert np.all(delta > 0.0)


def test_kalman_reset():
    est = KalmanResidualEstimator()
    est.estimate(np.ones((N, N)), np.zeros((N, N)))
    est.reset()
    # Tras reset, la siguiente medición vuelve a ser cruda.
    delta = est.estimate(np.full((N, N), 7.0), np.zeros((N, N)))
    assert np.allclose(delta, 7.0)


# ── Escala de Mbase a la ventana de comparación (Fase 5) ────────────────────────────────
def test_escalar_a_ventana_prorratea_por_fraccion_de_dia():
    diaria = np.full((N, N), 1440.0)  # 1440 "viajes" diarios por celda
    # Una ventana de 120 min = 1/12 del día → 120 por celda.
    ventana = baseline.escalar_a_ventana(diaria, 120)
    assert np.allclose(ventana, 120.0)


def test_escalar_a_ventana_dia_completo_es_identidad():
    diaria = np.arange(N * N, dtype=float).reshape(N, N)
    assert np.allclose(baseline.escalar_a_ventana(diaria, 1440), diaria)


# ── Mbase intradía (24, N, N) ──────────────────────────────────────────────────────────
def test_build_baseline_intradia_promedia_y_omite_vacios():
    a = np.ones((24, N, N))
    b = np.full((24, N, N), 3.0)
    mbase = baseline.build_baseline_intradia({"laboral": [a, b], "feriado": []})
    assert mbase["laboral"].shape == (24, N, N)
    assert np.allclose(mbase["laboral"], 2.0)
    assert "feriado" not in mbase


def test_baseline_ventana_intradia_suma_las_horas_cubiertas():
    # Tensor con 1.0 por celda en cada hora: una ventana de 120 min = 2 horas → 2.0 por celda.
    tensor = np.ones((24, N, N))
    ahora = datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc)  # ventana cubre 06:00–08:00
    ventana = baseline.baseline_ventana_intradia(tensor, ahora, 120)
    assert np.allclose(ventana, 2.0)


def test_baseline_ventana_intradia_usa_el_patron_de_la_hora():
    # La hora 7 carga 100; las demás 1. A las 08:00 con ventana 120 → cubre h6 (1) y h7 (100).
    tensor = np.ones((24, N, N))
    tensor[7] = 100.0
    ahora = datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc)
    ventana = baseline.baseline_ventana_intradia(tensor, ahora, 120)
    assert np.allclose(ventana, 101.0)


def test_construir_mbase_intradia_sintetico_estructura_y_niveles():
    mbase = historico.construir_mbase_intradia_sintetico(dias_por_tipo=2, semilla=0)
    assert set(mbase) == set(baseline.TIPOS_DIA)
    for tensor in mbase.values():
        assert tensor.shape == (24, N, N)
    assert mbase["laboral"].sum() > mbase["feriado"].sum()


# ── Estado combinado ────────────────────────────────────────────────────────────────────
def test_estado_m_hat_y_norma_con_mbase_real():
    mbase = np.full((N, N), 4.0)
    delta = np.full((N, N), 1.0)
    estado = state.construir_estado(mbase, delta)
    assert np.allclose(estado.m_hat, 5.0)
    assert estado.norma_delta == float(np.linalg.norm(delta))

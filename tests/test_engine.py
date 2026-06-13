"""Pruebas del núcleo matemático puro (sin FastAPI ni Redis)."""

from datetime import datetime, timezone

import numpy as np

from engine.demand import baseline, state
from engine.demand.residual import KalmanResidualEstimator
from engine.network import topology
from engine.optimizer import gating, milp
from engine.trip_chaining.chaining import reconstruir_od


def test_topologia_consistente():
    # Índices y nombres se corresponden 1:1.
    assert topology.N_ESTACIONES == len(topology.ESTACIONES)
    assert len(topology.INDICE_ESTACION) == topology.N_ESTACIONES
    # Las terminales son estaciones reales del corredor.
    for terminal in topology.TERMINALES:
        assert topology.es_estacion_valida(terminal)
        assert topology.es_terminal(terminal)


def test_servicios_solo_atienden_estaciones_reales():
    for servicio in topology.SERVICIOS:
        for parada in servicio.paradas:
            assert topology.es_estacion_valida(parada)


def test_trip_chaining_forma_od():
    od = reconstruir_od([])
    n = topology.N_ESTACIONES
    assert od.shape == (n, n)


def test_demanda_norma_cero_sin_residuo():
    mbase = baseline.matriz_vacia()
    est = KalmanResidualEstimator()
    delta = est.estimate(mbase, mbase)  # observado == base → ΔM = 0
    estado = state.construir_estado(mbase, delta)
    assert estado.norma_delta == 0.0
    assert np.array_equal(estado.m_hat, mbase)


def test_gating_dispara_por_umbral_y_por_incidencia():
    assert gating.debe_optimizar(norma_delta=200.0, epsilon=150.0) is True
    assert gating.debe_optimizar(norma_delta=10.0, epsilon=150.0) is False
    # Una incidencia fuerza la optimización aunque la norma sea baja.
    assert gating.debe_optimizar(norma_delta=0.0, epsilon=150.0, hay_incidencias=True) is True


def test_itinerario_base_despacha_desde_cada_terminal():
    plan = milp.itinerario_base(datetime.now(timezone.utc))
    assert plan.optimizado is False
    terminales = {d.terminal_salida for d in plan.despachos}
    assert terminales == set(topology.TERMINALES)

"""Pruebas del harness de simulación de saturación y contingencia (`engine/simulation`)."""

from datetime import datetime, timezone

import numpy as np

from engine.network import topology
from engine.optimizer import milp
from engine.simulation import (
    Modificadores,
    PerfilDemanda,
    RedConfig,
    hay_colapso,
    inject_transit_disruption,
    plan_a_capacidad_por_estacion,
    saturacion_max_por_estacion,
    simulate_step,
    simular_dia,
)

N = topology.N_ESTACIONES
AHORA = datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc)


# ── Núcleo: simulate_step ──────────────────────────────────────────────────────────────
def test_simulate_step_conservacion_y_cotas():
    rng = np.random.default_rng(0)
    q_prev = np.array([10.0, 0.0, 50.0])
    lam = np.array([5.0, 5.0, 5.0])
    cap = np.array([8.0, 8.0, 8.0])

    q_new, arr, srv = simulate_step(rng, q_prev, lam, cap)

    # Conservación exacta: lo que entra menos lo que se embarca queda en cola.
    assert np.allclose(q_new, q_prev + arr - srv)
    # Cotas del despeje: no se embarca más que lo disponible ni más que la capacidad.
    assert np.all(srv <= q_prev + arr + 1e-9)
    assert np.all(srv <= cap + 1e-9)
    assert np.all(q_new >= -1e-9)


def test_simulate_step_sin_capacidad_acumula_todo():
    rng = np.random.default_rng(1)
    q_prev = np.zeros(3)
    lam = np.array([10.0, 10.0, 10.0])
    cap = np.zeros(3)  # estación bloqueada
    q_new, arr, srv = simulate_step(rng, q_prev, lam, cap)
    assert np.allclose(srv, 0.0)
    assert np.allclose(q_new, arr)


# ── Configuración ──────────────────────────────────────────────────────────────────────
def test_aforo_por_rol():
    cfg = RedConfig.por_defecto(aforo_terminal=2000, aforo_hub=1000, aforo_regular=500)
    central = topology.INDICE_ESTACION[topology.TERMINAL_CENTRAL]
    assert cfg.aforo[central] == 2000                       # terminal/hub central
    # Hay estaciones de los tres niveles representadas.
    assert set(np.unique(cfg.aforo)) <= {2000.0, 1000.0, 500.0}
    assert cfg.aforo.min() == 500.0


# ── Puente plan → capacidad ────────────────────────────────────────────────────────────
def test_plan_a_capacidad():
    cfg = RedConfig.por_defecto()
    plan = milp.itinerario_base(AHORA)   # REG, 2 buses por terminal (8 en total)
    cap = plan_a_capacidad_por_estacion(plan, cfg)
    # REG atiende todas las estaciones; su capacidad se reparte entre sus 45 paradas.
    assert np.allclose(cap, 8 * cfg.capacidad_bus / topology.N_ESTACIONES)


# ── Día completo: reproducibilidad ─────────────────────────────────────────────────────
def test_simular_dia_reproducible_por_seed():
    cfg = RedConfig.por_defecto()
    perfil = PerfilDemanda.sintetico("laboral")
    plan = milp.itinerario_base(AHORA)

    a = simular_dia(perfil, plan, cfg, seed=42)
    b = simular_dia(perfil, plan, cfg, seed=42)
    c = simular_dia(perfil, plan, cfg, seed=7)

    assert np.array_equal(a.cola, b.cola)
    assert not np.array_equal(a.cola, c.cola)


# ── Contingencia: la disrupción agrava la saturación ───────────────────────────────────
def test_disrupcion_agrava_saturacion_y_colapsa():
    cfg = RedConfig.por_defecto()
    perfil = PerfilDemanda.sintetico("laboral")
    plan = milp.itinerario_base(AHORA)
    central = topology.INDICE_ESTACION[topology.TERMINAL_CENTRAL]

    base = simular_dia(perfil, plan, cfg, seed=3)

    mods = inject_transit_disruption(
        Modificadores.vacio(), topology.TERMINAL_CENTRAL,
        hora_inicio=8, duracion_h=3, reduccion_pct=85.0,
    )
    disrupt = simular_dia(perfil, plan, cfg, mods=mods, seed=3)

    sat_base = saturacion_max_por_estacion(base)[central]
    sat_disrupt = saturacion_max_por_estacion(disrupt)[central]
    assert sat_disrupt > sat_base
    assert hay_colapso(disrupt)


def test_backpressure_monotono_en_vecinos():
    central = topology.INDICE_ESTACION[topology.TERMINAL_CENTRAL]
    suave = inject_transit_disruption(
        Modificadores.vacio(), topology.TERMINAL_CENTRAL, 8, 1, reduccion_pct=40.0)
    fuerte = inject_transit_disruption(
        Modificadores.vacio(), topology.TERMINAL_CENTRAL, 8, 1, reduccion_pct=80.0)
    # En el vecino inmediato, mayor reducción ⇒ menor capacidad disponible.
    assert fuerte.cap_factor[8, central + 1] < suave.cap_factor[8, central + 1]

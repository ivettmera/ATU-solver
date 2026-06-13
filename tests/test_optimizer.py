"""Pruebas del optimizador MILP (Fase 3)."""

from datetime import datetime, timezone

import numpy as np

from engine.network import topology
from engine.optimizer import milp

I = topology.INDICE_ESTACION
N = topology.N_ESTACIONES
AHORA = datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc)

# Restricciones de referencia para las pruebas.
RES = milp.RestriccionesFlota(
    flota_total=120, conductores_disponibles=140, capacidad_bus=160, max_despachos=20,
)


def _od_en(o: str, d: str, carga: float) -> np.ndarray:
    m = np.zeros((N, N))
    m[I[o], I[d]] = carga
    return m


# ── Asignación de demanda a servicios ──────────────────────────────────────────────────
def test_asignacion_particiona_la_demanda_sin_doble_conteo():
    # Pares variados; la suma asignada debe igualar la demanda total.
    m = np.zeros((N, N))
    m[I["Terminal Naranjal"], I["Estación Central"]] = 100  # lo atiende expreso
    m[I["Los Incas"], I["Universidad"]] = 40                # solo Regular (extensión norte)
    asignada = milp.asignar_demanda_a_servicios(m)
    assert abs(sum(asignada.values()) - 140.0) < 1e-9


def test_par_expreso_se_asigna_al_servicio_mas_expreso():
    # Naranjal→Angamos lo atienden ambos expresos (menos paradas que el Regular).
    m = _od_en("Terminal Naranjal", "Angamos", 50)
    asignada = milp.asignar_demanda_a_servicios(m)
    assert asignada["REG"] == 0.0
    assert asignada["EXP_A"] + asignada["EXP_B"] == 50.0


def test_par_de_extension_solo_lo_cubre_regular():
    m = _od_en("Los Incas", "22 de Agosto", 30)
    asignada = milp.asignar_demanda_a_servicios(m)
    assert asignada["REG"] == 30.0
    assert asignada["EXP_A"] == 0.0 and asignada["EXP_B"] == 0.0


# ── Factor de capacidad por incidencias ──────────────────────────────────────────────────
def test_incidencia_en_estacion_compartida_reduce_capacidad():
    # Estación Central está en las tres rutas → bloqueo anula su capacidad efectiva.
    inc = [milp.IncidenciaOperativa(estacion="Estación Central", bloqueado=True)]
    factor = milp.factor_capacidad_por_servicio(inc)
    assert factor["REG"] == 0.0 and factor["EXP_A"] == 0.0 and factor["EXP_B"] == 0.0


def test_incidencia_parcial_solo_afecta_servicios_de_esa_ruta():
    # Capacidad reducida 50% en una estación solo del Regular (extensión norte).
    inc = [milp.IncidenciaOperativa(estacion="Los Incas", capacidad_reducida_pct=50.0)]
    factor = milp.factor_capacidad_por_servicio(inc)
    assert factor["REG"] == 0.5
    assert factor["EXP_A"] == 1.0 and factor["EXP_B"] == 1.0


# ── Resolución MILP ────────────────────────────────────────────────────────────────────
def _total_buses(plan) -> int:
    return sum(d.num_buses for d in plan.despachos)


def test_milp_optimiza_y_respeta_la_flota():
    m = _od_en("Los Incas", "Universidad", 8000)  # demanda alta sobre el Regular
    plan = milp.resolver_despacho(AHORA, m, RES, norma_delta=500.0)
    assert plan.optimizado is True
    assert _total_buses(plan) <= min(RES.flota_total, RES.conductores_disponibles)
    assert _total_buses(plan) > 0


def test_mas_demanda_implica_mas_buses():
    baja = milp.resolver_despacho(AHORA, _od_en("Los Incas", "Universidad", 800), RES, 200.0)
    alta = milp.resolver_despacho(AHORA, _od_en("Los Incas", "Universidad", 6000), RES, 600.0)
    assert _total_buses(alta) > _total_buses(baja)


def test_bloqueo_total_del_corredor_no_despacha_buses_inutiles():
    # Si Estación Central está bloqueada, ningún servicio tiene capacidad efectiva:
    # despachar buses no sirve, así que el óptimo es no malgastar flota.
    m = _od_en("Terminal Naranjal", "Terminal Matellini", 5000)
    inc = [milp.IncidenciaOperativa(estacion="Estación Central", bloqueado=True)]
    plan = milp.resolver_despacho(AHORA, m, RES, 400.0, incidencias=inc)
    assert plan.optimizado is True
    assert _total_buses(plan) == 0


# ── Objetivo minimax vs. suma ─────────────────────────────────────────────────────────
def _peor_cola(plan, demanda: dict, cap_bus: int) -> float:
    """Mayor demanda no servida entre los servicios, dado el plan (sin incidencias)."""
    buses = {s.codigo: 0 for s in topology.SERVICIOS}
    for d in plan.despachos:
        buses[d.servicio] += d.num_buses
    return max(max(0.0, demanda[c] - buses[c] * cap_bus) for c in demanda)


def test_minimax_baja_la_peor_cola_frente_a_suma_con_flota_escasa():
    # Demanda comparable entre rutas y flota insuficiente: hay que racionar.
    m = np.zeros((N, N))
    m[I["Los Incas"], I["22 de Agosto"]] = 500        # solo Regular
    m[I["México"], I["Javier Prado"]] = 480           # solo Expreso A
    m[I["Canadá"], I["Ricardo Palma"]] = 460          # solo Expreso B
    demanda = milp.asignar_demanda_a_servicios(m)
    assert demanda["REG"] == 500 and demanda["EXP_A"] == 480 and demanda["EXP_B"] == 460

    escasa = milp.RestriccionesFlota(
        flota_total=6, conductores_disponibles=6, capacidad_bus=160, max_despachos=20)

    plan_suma = milp.resolver_despacho(AHORA, m, escasa, 0.0, objetivo="suma")
    plan_mm = milp.resolver_despacho(AHORA, m, escasa, 0.0, objetivo="minimax")

    # Misma flota gastada, pero el minimax reparte y deja una peor cola más baja.
    assert _total_buses(plan_mm) <= 6 and _total_buses(plan_suma) <= 6
    assert _peor_cola(plan_mm, demanda, 160) < _peor_cola(plan_suma, demanda, 160)

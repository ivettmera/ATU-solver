"""Pruebas de reconstrucción de la matriz OD (trip chaining + cierre de lazo)."""

from datetime import datetime, timezone

import numpy as np

from engine.network import topology
from engine.trip_chaining import synthetic
from engine.trip_chaining.chaining import (
    EventoViaje,
    reconstruir_od,
    reconstruir_od_por_hora,
)

I = topology.INDICE_ESTACION


def _ev(tarjeta: str, hora: int, estacion: str) -> EventoViaje:
    ts = datetime(2026, 6, 13, hora, 0, tzinfo=timezone.utc)
    return EventoViaje(tarjeta_id=tarjeta, timestamp=ts, estacion_origen=estacion)


def test_caso_manual_encadenamiento_y_cierre():
    # Una tarjeta con dos ingresos: UNI (mañana) y Caquetá (tarde).
    # Encadenamiento → destino(UNI)=Caquetá; cierre de lazo → destino(Caquetá)=UNI.
    eventos = [_ev("A", 8, "UNI"), _ev("A", 18, "Caquetá")]
    od = reconstruir_od(eventos)

    assert od[I["UNI"], I["Caquetá"]] == 1.0
    assert od[I["Caquetá"], I["UNI"]] == 1.0
    assert od.sum() == 2.0  # exactamente dos pares OD


def test_ordena_por_timestamp_aunque_lleguen_desordenados():
    # Mismos eventos en orden inverso de llegada: el resultado no debe cambiar.
    eventos = [_ev("A", 18, "Caquetá"), _ev("A", 8, "UNI")]
    od = reconstruir_od(eventos)
    assert od[I["UNI"], I["Caquetá"]] == 1.0
    assert od[I["Caquetá"], I["UNI"]] == 1.0


def test_descarta_tarjetas_con_un_solo_viaje():
    # Un único ingreso no permite inferir destino → no aporta a la OD.
    od = reconstruir_od([_ev("solo", 9, "Terminal Naranjal")])
    assert od.sum() == 0.0


def test_reconstruccion_exacta_con_cierre_garantizado():
    # Si todos los usuarios cierran el lazo, la OD reconstruida == la ground-truth.
    eventos, od_real = synthetic.generar_dia(n_usuarios=300, semilla=7, prob_cierre=1.0)
    od_rec = reconstruir_od(eventos)
    assert np.array_equal(od_rec, od_real)


def test_alta_exactitud_con_usuarios_que_no_cierran():
    # Con un 15% de usuarios que no cierran lazo, el chaining sigue recuperando la mayoría.
    eventos, od_real = synthetic.generar_dia(n_usuarios=1000, semilla=11, prob_cierre=0.85)
    od_rec = reconstruir_od(eventos)

    # La masa total de viajes se conserva (mismo nº de pares OD).
    assert od_rec.sum() == od_real.sum()

    # Acuerdo celda a celda (intersección / total) por encima del 85%.
    acuerdo = np.minimum(od_rec, od_real).sum() / od_real.sum()
    assert acuerdo >= 0.85


# ── Reconstrucción intradía (por hora de abordaje) ──────────────────────────────────────
def test_od_por_hora_suma_reproduce_la_od_diaria():
    eventos, _ = synthetic.generar_dia(n_usuarios=400, semilla=5)
    por_hora = reconstruir_od_por_hora(eventos)
    assert por_hora.shape == (24, topology.N_ESTACIONES, topology.N_ESTACIONES)
    assert np.array_equal(por_hora.sum(axis=0), reconstruir_od(eventos))


def test_od_por_hora_ubica_el_par_en_la_hora_de_abordaje():
    # Aborda en UNI a las 8 y en Caquetá a las 18: el primer par cuenta en la hora 8.
    eventos = [_ev("A", 8, "UNI"), _ev("A", 18, "Caquetá")]
    por_hora = reconstruir_od_por_hora(eventos)
    assert por_hora[8, I["UNI"], I["Caquetá"]] == 1.0      # viaje de ida, abordaje 08h
    assert por_hora[18, I["Caquetá"], I["UNI"]] == 1.0     # cierre de lazo, abordaje 18h

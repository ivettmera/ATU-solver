"""Pruebas de la topología real del Metropolitano (Fase 3)."""

from engine.network import topology

I = topology.INDICE_ESTACION


def test_extremos_y_hub_central():
    assert topology.ESTACIONES[0] == "Terminal Chimpu Ocllo"
    assert topology.ESTACIONES[-1] == "Terminal Matellini"
    assert "Estación Central" in I


def test_orden_norte_sur_de_hubs():
    # El índice crece de norte a sur: Naranjal antes que Central antes que Matellini.
    assert I["Terminal Naranjal"] < I["Estación Central"] < I["Terminal Matellini"]
    # Algunos hitos del tramo sur en orden.
    assert I["Javier Prado"] < I["Angamos"] < I["Benavides"]


def test_terminales_son_estaciones_validas():
    assert len(topology.TERMINALES) == 4
    for t in topology.TERMINALES:
        assert topology.es_estacion_valida(t)
        assert topology.es_terminal(t)


def test_servicios_atienden_solo_estaciones_reales():
    for s in topology.SERVICIOS:
        for parada in s.paradas:
            assert topology.es_estacion_valida(parada)


def test_terminales_de_servicio_regular_incluye_todos():
    regular = topology.SERVICIOS_POR_CODIGO["REG"]
    assert set(topology.terminales_de_servicio(regular)) == set(topology.TERMINALES)
    # Los expresos no nacen en la extensión norte (Chimpu Ocllo).
    exp_a = topology.SERVICIOS_POR_CODIGO["EXP_A"]
    assert topology.TERMINAL_NORTE not in topology.terminales_de_servicio(exp_a)

"""Pruebas de la tabla de despacho precalculada (`engine/optimizer/precompute`)."""

from datetime import datetime, timezone

from engine.demand import baseline, historico
from engine.optimizer import milp, precompute

AHORA = datetime(2026, 6, 13, 8, 0, tzinfo=timezone.utc)
RES = milp.RestriccionesFlota(
    flota_total=120, conductores_disponibles=140, capacidad_bus=160, max_despachos=20,
)


def _tabla():
    mbase_intradia = historico.construir_mbase_intradia_sintetico(dias_por_tipo=2, semilla=0)
    return mbase_intradia, precompute.construir_tabla_despacho(mbase_intradia, RES)


def _buses(decisiones) -> int:
    return sum(d["num_buses"] for d in decisiones)


def test_tabla_tiene_todos_los_tipos_y_24_horas():
    _, tabla = _tabla()
    assert set(tabla) == set(baseline.TIPOS_DIA)
    for por_hora in tabla.values():
        assert set(por_hora) == set(range(24))


def test_serializacion_roundtrip_normaliza_horas_a_int():
    _, tabla = _tabla()
    recuperada = precompute.tabla_desde_json(precompute.tabla_a_json(tabla))
    assert recuperada == tabla
    # Las claves de hora vuelven a ser int (JSON las guarda como str).
    assert all(isinstance(h, int) for h in recuperada["laboral"])


def test_materializar_plan_sella_con_la_hora_actual():
    _, tabla = _tabla()
    decisiones = tabla["laboral"][8]
    plan = precompute.materializar_plan(decisiones, AHORA, norma_delta=0.0)
    assert plan.optimizado is False                      # caso base servido por lookup
    assert plan.calculado_en == AHORA
    assert len(plan.despachos) == len(decisiones)
    assert all(d.hora_salida == AHORA for d in plan.despachos)


def test_plan_precalculado_es_pico_consciente():
    mbase_intradia, tabla = _tabla()
    laboral = tabla["laboral"]
    h_pico = int(mbase_intradia["laboral"].sum(axis=(1, 2)).argmax())
    # En el pico se despachan más buses que en la madrugada (hora 3, sin demanda).
    assert _buses(laboral[h_pico]) > _buses(laboral[3])

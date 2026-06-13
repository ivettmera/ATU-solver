"""Pruebas de la lógica de difusión por cambio de plan (Fase 4)."""

from app.core.scheduler import _firma_plan


def _payload(optimizado, recs):
    return {
        "calculado_en": "2026-06-13T08:00:00Z",
        "norma_delta": 0.0,
        "optimizado": optimizado,
        "recomendaciones": [
            {"servicio": s, "terminal_salida": t, "num_buses": n, "motivo": "BASE"}
            for (s, t, n) in recs
        ],
    }


def test_misma_decision_distinto_timestamp_misma_firma():
    a = _payload(False, [("REG", "Estación Central", 2)])
    b = _payload(False, [("REG", "Estación Central", 2)])
    b["calculado_en"] = "2026-06-13T08:05:00Z"  # otro instante
    b["norma_delta"] = 42.0                       # otra norma
    assert _firma_plan(a) == _firma_plan(b)


def test_firma_es_invariante_al_orden_de_recomendaciones():
    a = _payload(True, [("REG", "Terminal Naranjal", 3), ("EXP_A", "Estación Central", 1)])
    b = _payload(True, [("EXP_A", "Estación Central", 1), ("REG", "Terminal Naranjal", 3)])
    assert _firma_plan(a) == _firma_plan(b)


def test_cambio_de_optimizado_cambia_firma():
    base = _payload(False, [("REG", "Estación Central", 2)])
    opt = _payload(True, [("REG", "Estación Central", 2)])
    assert _firma_plan(base) != _firma_plan(opt)


def test_cambio_de_num_buses_cambia_firma():
    a = _payload(True, [("REG", "Estación Central", 2)])
    b = _payload(True, [("REG", "Estación Central", 5)])
    assert _firma_plan(a) != _firma_plan(b)

"""Validación de los contratos Pydantic en el borde de la API."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.api.v1.schemas import IncidentReport, TurnstileEvent
from engine.network import topology


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def test_turnstile_event_estacion_valida():
    ev = TurnstileEvent(
        tarjeta_id="T-1",
        timestamp_entrada=_ahora(),
        estacion_origen=topology.ESTACIONES[0],
    )
    assert ev.estacion_origen == topology.ESTACIONES[0]


def test_turnstile_event_rechaza_estacion_desconocida():
    with pytest.raises(ValidationError):
        TurnstileEvent(
            tarjeta_id="T-1",
            timestamp_entrada=_ahora(),
            estacion_origen="Estacion Fantasma",
        )


def test_incident_porcentaje_fuera_de_rango():
    with pytest.raises(ValidationError):
        IncidentReport(
            estacion_id=topology.TERMINAL_CENTRAL,
            tipo="BLOQUEO",
            severidad="ALTA",
            capacidad_reducida_porcentaje=150.0,  # > 100
        )


def test_incident_tipo_invalido():
    with pytest.raises(ValidationError):
        IncidentReport(
            estacion_id=topology.TERMINAL_CENTRAL,
            tipo="METEORITO",  # no está en el Literal
            severidad="ALTA",
        )

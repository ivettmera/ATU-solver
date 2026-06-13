"""
Harness de simulación de saturación y contingencia del corredor del Metropolitano.

Banco de pruebas (no servicio) para validar que un plan de despacho mantiene las estaciones bajo
control y que un re-plan de contingencia evita el colapso ante un incidente. Ver `README.md`.
"""

from engine.simulation.config import RedConfig
from engine.simulation.demanda_perfil import PerfilDemanda
from engine.simulation.engine import SimResult, simular_dia, simulate_step
from engine.simulation.incidentes import (
    Modificadores,
    inject_external_event,
    inject_transit_disruption,
)
from engine.simulation.metricas import hay_colapso, resumen, saturacion_max_por_estacion
from engine.simulation.plan_capacidad import (
    capacidad_por_hora,
    plan_a_capacidad_por_estacion,
)

__all__ = [
    "RedConfig",
    "PerfilDemanda",
    "SimResult",
    "simular_dia",
    "simulate_step",
    "Modificadores",
    "inject_transit_disruption",
    "inject_external_event",
    "plan_a_capacidad_por_estacion",
    "capacidad_por_hora",
    "saturacion_max_por_estacion",
    "hay_colapso",
    "resumen",
]

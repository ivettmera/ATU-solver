"""
Estructura del plan de despacho — resultado del optimizador.

Es la representación interna (desacoplada de Pydantic) que produce el solver MILP o el
itinerario base. La capa `app/` la traduce a los schemas de respuesta de la API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Despacho:
    """Una orden de salida: cuántos buses de qué servicio salen de qué terminal y cuándo."""

    servicio: str          # código de servicio (REG, EXP_A, EXP_B)
    terminal_salida: str   # Naranjal | Estacion Central | Matellini
    hora_salida: datetime
    num_buses: int


@dataclass(frozen=True)
class DispatchPlan:
    """Plan de despacho completo para el horizonte actual."""

    calculado_en: datetime
    norma_delta: float
    optimizado: bool                      # True si lo resolvió el MILP; False si es itinerario base
    despachos: list[Despacho] = field(default_factory=list)

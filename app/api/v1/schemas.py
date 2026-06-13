"""
Contratos de la API (Pydantic v2).

Tipado fuerte de las entradas/salidas para blindar el álgebra lineal posterior: si un evento
trae una estación inexistente o un porcentaje fuera de rango, se rechaza en el borde y nunca
llega al núcleo matemático. Estos modelos son el contrato que consumen las apps móviles y el
frontend en paralelo, sin conocer la matemática interna del despacho.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from engine.network import topology


# ── 1. Ingesta de telemetría ─────────────────────────────────────────────────────────
class TurnstileEvent(BaseModel):
    """Un evento de ingreso a un torniquete (no hay evento de salida en el sistema)."""

    tarjeta_id: str = Field(..., examples=["TARJ-0001A"])
    timestamp_entrada: datetime
    estacion_origen: str = Field(..., examples=["Estacion Central"])

    @field_validator("estacion_origen")
    @classmethod
    def _validar_estacion(cls, v: str) -> str:
        if not topology.es_estacion_valida(v):
            raise ValueError(f"Estación desconocida: '{v}'")
        return v


class TelemetryPayload(BaseModel):
    """Lote de eventos enviado por la red de torniquetes (cada ~5 min)."""

    timestamp_envio: datetime
    eventos: list[TurnstileEvent]


class IngressResponse(BaseModel):
    estado: Literal["ok"] = "ok"
    eventos_recibidos: int
    ventana: str = Field(..., description="Clave de la ventana de 5 min donde se almacenaron")


# ── 2. Incidencias ───────────────────────────────────────────────────────────────────
class IncidentReport(BaseModel):
    """Bloqueo, accidente o andén colapsado reportado manualmente por operaciones."""

    estacion_id: str = Field(..., examples=["Estacion Central"])
    tipo: Literal["BLOQUEO", "ACCIDENTE", "ANDEN_COLAPSADO"]
    severidad: Literal["BAJA", "MEDIA", "ALTA"]
    bloqueado: bool = False
    capacidad_reducida_porcentaje: float = Field(0.0, ge=0.0, le=100.0)

    @field_validator("estacion_id")
    @classmethod
    def _validar_estacion(cls, v: str) -> str:
        if not topology.es_estacion_valida(v):
            raise ValueError(f"Estación desconocida: '{v}'")
        return v


class IncidentResponse(BaseModel):
    estado: Literal["registrada"] = "registrada"
    estacion_id: str
    recalculo_forzado: bool = Field(
        ..., description="True si la incidencia dispara un recálculo MILP inmediato"
    )


# ── 3. Decisiones de despacho ────────────────────────────────────────────────────────
class DispatchRecommendation(BaseModel):
    """Una orden de salida sugerida."""

    servicio: str = Field(..., examples=["REG"])
    terminal_salida: str = Field(..., examples=["Estacion Central"])
    hora_salida: datetime
    num_buses: int = Field(..., ge=0)
    motivo: Literal["BASE", "OPTIMIZADO"]


class DispatchPlan(BaseModel):
    """Plan de despacho completo devuelto por la API y empujado por WebSocket."""

    calculado_en: datetime
    norma_delta: float = Field(..., description="‖ΔM(t)‖₂ que originó este plan")
    optimizado: bool = Field(..., description="True si lo resolvió el MILP")
    recomendaciones: list[DispatchRecommendation]

    @classmethod
    def desde_engine(cls, plan) -> "DispatchPlan":
        """Traduce un `engine.optimizer.dispatch_plan.DispatchPlan` a este contrato."""
        motivo = "OPTIMIZADO" if plan.optimizado else "BASE"
        recomendaciones = [
            DispatchRecommendation(
                servicio=d.servicio,
                terminal_salida=d.terminal_salida,
                hora_salida=d.hora_salida,
                num_buses=d.num_buses,
                motivo=motivo,
            )
            for d in plan.despachos
        ]
        return cls(
            calculado_en=plan.calculado_en,
            norma_delta=plan.norma_delta,
            optimizado=plan.optimizado,
            recomendaciones=recomendaciones,
        )

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class PrediccionRequest(BaseModel):
    estacion: str = Field(..., examples=["Javier Prado"])
    fecha_inicio: date = Field(default_factory=date.today)
    dias: int = Field(default=7, ge=1, le=30)
    disponibilidad_chofer: float = Field(default=0.95, ge=0.0, le=1.0)


class PrediccionDia(BaseModel):
    fecha: date
    prediccion: int
    intervalo_inferior: int
    intervalo_superior: int


class PrediccionResponse(BaseModel):
    estacion: str
    predicciones: list[PrediccionDia]


class CuelloBotella(BaseModel):
    estacion: str
    fecha: date
    prediccion: int
    carga_pct: float
    cuello_botella: bool


class CuellosRequest(BaseModel):
    fecha_inicio: date = Field(default_factory=date.today)
    dias: int = Field(default=7, ge=1, le=30)
    disponibilidad_chofer: float = Field(default=0.90, ge=0.0, le=1.0)
    umbral_pct: float = Field(default=85.0, ge=0.0, le=100.0)


class CuellosResponse(BaseModel):
    total_cuellos: int
    cuellos: list[CuelloBotella]

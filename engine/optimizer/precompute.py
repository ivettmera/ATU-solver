"""
Tabla de despacho precalculada — "el entrenamiento".

Resuelve el MILP **offline** una vez por `(tipo_día, hora)` usando el Mbase intradía y guarda el
plan resultante. En runtime, el caso base del gating (sin anomalía ni incidencias) se sirve con un
**lookup O(1)** de esta tabla en vez de recalcular: el plan base deja de ser un itinerario fijo y
pasa a ser el plan **pico-consciente** de la hora. El MILP online se reserva para las desviaciones
reales (`‖ΔM‖₂ > ε`) e incidencias.

La tabla se serializa como `{tipo_día: {hora: [decisión, ...]}}`, donde cada decisión es
`{servicio, terminal_salida, num_buses}` (sin timestamp: el runtime lo re-sella con la hora actual).
"""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np

from engine.optimizer.dispatch_plan import Despacho, DispatchPlan
from engine.optimizer.milp import OBJETIVO_DEFECTO, RestriccionesFlota, resolver_despacho

# Clave de Redis donde se cachea la tabla completa.
CLAVE_TABLA = "dispatch:tabla"

# Timestamp placeholder para el solve offline; el runtime re-sella con la hora real.
_REF = datetime(2000, 1, 1)


def construir_tabla_despacho(
    mbase_intradia: dict[str, np.ndarray],
    restricciones: RestriccionesFlota,
    objetivo: str = OBJETIVO_DEFECTO,
) -> dict[str, dict[int, list[dict]]]:
    """
    Resuelve el MILP por `(tipo_día, hora)` y devuelve la tabla de decisiones.

    Args:
        mbase_intradia: tipo_día → tensor OD `(24, N, N)`.
        restricciones: recursos de flota/conductores/headway.
        objetivo: "minimax" | "suma" (ver `milp.resolver_despacho`).
    """
    tabla: dict[str, dict[int, list[dict]]] = {}
    for tipo_dia, tensor in mbase_intradia.items():
        por_hora: dict[int, list[dict]] = {}
        for h in range(tensor.shape[0]):
            plan = resolver_despacho(_REF, tensor[h], restricciones, 0.0, objetivo=objetivo)
            por_hora[h] = [
                {"servicio": d.servicio, "terminal_salida": d.terminal_salida,
                 "num_buses": d.num_buses}
                for d in plan.despachos
            ]
        tabla[tipo_dia] = por_hora
    return tabla


def tabla_a_json(tabla: dict) -> str:
    """Serializa la tabla a JSON para Redis."""
    return json.dumps(tabla)


def tabla_desde_json(texto: str) -> dict[str, dict[int, list[dict]]]:
    """Deserializa la tabla; normaliza las claves de hora (JSON las guarda como str) a int."""
    crudo = json.loads(texto)
    return {
        tipo_dia: {int(h): decisiones for h, decisiones in por_hora.items()}
        for tipo_dia, por_hora in crudo.items()
    }


def materializar_plan(
    decisiones: list[dict],
    ahora: datetime,
    norma_delta: float = 0.0,
) -> DispatchPlan:
    """Construye un `DispatchPlan` (sellado con `ahora`) desde las decisiones almacenadas."""
    despachos = [
        Despacho(
            servicio=d["servicio"],
            terminal_salida=d["terminal_salida"],
            hora_salida=ahora,
            num_buses=d["num_buses"],
        )
        for d in decisiones
    ]
    return DispatchPlan(
        calculado_en=ahora,
        norma_delta=norma_delta,
        optimizado=False,   # caso base del gating: servido por lookup, sin MILP online
        despachos=despachos,
    )

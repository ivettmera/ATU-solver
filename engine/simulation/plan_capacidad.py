"""
Puente optimizador → simulador: traduce un `DispatchPlan` a capacidad de embarque por estación.

El plan de despacho (variable que controla el administrador) dice cuántos buses de cada servicio
salen. Un bus llena ~una vez su capacidad a lo largo del recorrido, así que la **capacidad de
embarque de un servicio se reparte entre sus paradas** (un expreso, con menos paradas, concentra más
capacidad por estación). La capacidad de embarque por estación es, en primera aproximación:

    cap[s] = Σ_{servicios que paran en s}  buses_servicio · capacidad_bus / nº_paradas_servicio

(modelo agregado por estación; la propagación mesoscópica entre estaciones queda como refinamiento).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from engine.network import topology
from engine.optimizer.dispatch_plan import DispatchPlan
from engine.simulation.config import RedConfig


def buses_por_servicio(plan: DispatchPlan) -> dict[str, int]:
    """Suma los buses despachados por servicio en un plan (agrega sobre terminales)."""
    out: dict[str, int] = defaultdict(int)
    for d in plan.despachos:
        out[d.servicio] += d.num_buses
    return dict(out)


def plan_a_capacidad_por_estacion(plan: DispatchPlan, config: RedConfig) -> np.ndarray:
    """Capacidad de embarque por estación (N,) para un plan, en pasajeros/hora."""
    n = topology.N_ESTACIONES
    cap = np.zeros(n, dtype=float)
    bps = buses_por_servicio(plan)
    for s in topology.SERVICIOS:
        b = bps.get(s.codigo, 0)
        if b <= 0:
            continue
        paradas = s.indices_paradas()
        aporte = b * config.capacidad_bus / len(paradas)   # capacidad repartida entre paradas
        for idx in paradas:
            cap[idx] += aporte
    return cap


def capacidad_por_hora(
    plan_por_hora: dict[int, DispatchPlan] | DispatchPlan,
    config: RedConfig,
) -> np.ndarray:
    """
    Capacidad por estación y hora `(24, N)`.

    Acepta un dict `{hora: plan}` o un único plan aplicado a todas las horas.
    """
    n = topology.N_ESTACIONES
    cap = np.zeros((24, n), dtype=float)
    if isinstance(plan_por_hora, DispatchPlan):
        fila = plan_a_capacidad_por_estacion(plan_por_hora, config)
        cap[:] = fila
        return cap
    for h in range(24):
        plan = plan_por_hora.get(h)
        if plan is not None:
            cap[h] = plan_a_capacidad_por_estacion(plan, config)
    return cap

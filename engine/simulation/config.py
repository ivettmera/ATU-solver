"""
Configuración estática de la red para el harness de simulación.

Reúne los parámetros que decide el **administrador** (no se observan de los datos): el **aforo**
(capacidad de andén) de cada estación y la capacidad/headway de los buses. El aforo se parametriza
por **rol** de estación —terminal, hub (atendido por un expreso) o regular—, porque no hay datos de
m² reales; al llegar mediciones, basta sustituir el vector `aforo`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.network import topology


def _indices_express() -> set[int]:
    """Índices de estaciones que atiende algún servicio expreso (hubs de mayor demanda)."""
    idx: set[int] = set()
    for s in topology.SERVICIOS:
        if s.codigo != "REG":
            idx.update(s.indices_paradas())
    return idx


@dataclass(frozen=True)
class RedConfig:
    """Parámetros estáticos de la red para la simulación."""

    aforo: np.ndarray            # (N,) capacidad de andén por estación (pasajeros en cola)
    capacidad_bus: int = 160     # pasajeros por bus (Settings.CAPACIDAD_BUS)
    headway_min: int = 3         # intervalo mínimo entre salidas de un servicio

    @classmethod
    def por_defecto(
        cls,
        aforo_terminal: float = 2000.0,
        aforo_hub: float = 1000.0,
        aforo_regular: float = 500.0,
        capacidad_bus: int = 160,
        headway_min: int = 3,
    ) -> "RedConfig":
        """Construye el aforo por rol de estación a partir de la topología."""
        n = topology.N_ESTACIONES
        terminales = {topology.INDICE_ESTACION[t] for t in topology.TERMINALES}
        express = _indices_express()

        aforo = np.full(n, aforo_regular, dtype=float)
        for i in range(n):
            if i in terminales:
                aforo[i] = aforo_terminal
            elif i in express:
                aforo[i] = aforo_hub
        return cls(aforo=aforo, capacidad_bus=capacidad_bus, headway_min=headway_min)

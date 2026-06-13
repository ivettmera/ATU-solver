"""
Mecanismo de guarda (gating).

Protege el servidor de correr el MILP (NP-duro) en cada ventana. El solver solo se invoca
cuando el sistema está fuera de su régimen normal:

    - Caso normal  (‖ΔM(t)‖₂ ≤ ε  y  sin incidencias)  → usar itinerario base, CPU cero.
    - Caso anomalía (‖ΔM(t)‖₂ >  ε  o  hay incidencia)  → ejecutar MILP.

Esto da degradación elegante: si la telemetría falla, ΔM≈0 y el sistema opera con seguridad
sobre el itinerario histórico.
"""

from __future__ import annotations


def debe_optimizar(
    norma_delta: float,
    epsilon: float,
    hay_incidencias: bool = False,
) -> bool:
    """
    Decide si se debe ejecutar el solver MILP.

    Args:
        norma_delta: ‖ΔM(t)‖₂, magnitud de la anomalía de demanda.
        epsilon: umbral de disparo (configurable, `Settings.EPSILON`).
        hay_incidencias: True si hay incidencias activas que fuerzan el recálculo.

    Returns:
        True si procede optimizar; False si basta el itinerario base.
    """
    return hay_incidencias or norma_delta > epsilon

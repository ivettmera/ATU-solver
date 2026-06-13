"""
Topología del corredor troncal del Metropolitano de Lima.

Corredor lineal de norte (Terminal Chimpu Ocllo) a sur (Terminal Matellini), con la Estación
Central como hub intermedio de transferencia y despacho. Sobre el eje circulan varios servicios
que saltan paradas (Regular, Expreso A, Expreso B). Los buses se despachan desde los terminales
de los extremos, el hub norte (Naranjal, origen histórico de la mayoría de expresos) y Central.

Lista de estaciones en orden norte→sur según el trazado troncal vigente (incluye las
extensiones norte —Chimpu Ocllo↔Naranjal— y sur —Estadio Unión↔Matellini—).
Fuente: Wikipedia "Metropolitano (Lima)" (consultado 2026-06).

Este módulo es la fuente única de verdad de la red: el índice en `ESTACIONES` es el índice de
fila/columna en todas las matrices OD del `engine/`.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Estaciones del corredor troncal, ordenadas de NORTE a SUR ─────────────────────────
ESTACIONES: list[str] = [
    # Extensión norte
    "Terminal Chimpu Ocllo",   # 0  — terminal norte
    "Los Incas",               # 1
    "Andrés Belaunde",         # 2
    "22 de Agosto",            # 3
    "Las Vegas",               # 4
    "Universidad",             # 5
    "Terminal Naranjal",       # 6  — hub norte (origen de expresos)
    # Tramo norte-centro
    "Izaguirre",               # 7
    "Pacífico",                # 8
    "Independencia",           # 9
    "Los Jazmines",            # 10
    "Tomás Valle",             # 11
    "El Milagro",              # 12
    "Honorio Delgado",         # 13
    "UNI",                     # 14
    "Parque del Trabajo",      # 15
    "Caquetá",                 # 16
    "Dos de Mayo",             # 17
    "Ramón Castilla",          # 18
    "Quilca",                  # 19
    "Tacna",                   # 20
    "España",                  # 21
    "Jirón de la Unión",       # 22
    "Colmena",                 # 23
    "Estación Central",        # 24 — HUB central de despacho
    # Tramo centro-sur
    "Estadio Nacional",        # 25
    "México",                  # 26
    "Canadá",                  # 27
    "Javier Prado",            # 28
    "Andrés Reyes",            # 29
    "Canaval y Moreyra",       # 30
    "Comunidad Andina-Aramburú",  # 31
    "Domingo Orué",            # 32
    "Angamos",                 # 33
    "Ricardo Palma",           # 34
    "Benavides",               # 35
    "28 de Julio",             # 36
    "Plaza de Flores",         # 37
    "Balta",                   # 38
    "Bulevar",                 # 39
    # Extensión sur
    "Estadio Unión",           # 40
    "Escuela Militar",         # 41
    "Terán",                   # 42
    "Rosario de Villa",        # 43
    "Terminal Matellini",      # 44 — terminal sur
]

N_ESTACIONES: int = len(ESTACIONES)

# Mapa nombre → índice, para validación y construcción de matrices.
INDICE_ESTACION: dict[str, int] = {nombre: i for i, nombre in enumerate(ESTACIONES)}

# ── Terminales desde donde se despachan buses ────────────────────────────────────────
TERMINAL_NORTE = "Terminal Chimpu Ocllo"
TERMINAL_HUB_NORTE = "Terminal Naranjal"
TERMINAL_CENTRAL = "Estación Central"
TERMINAL_SUR = "Terminal Matellini"
TERMINALES: list[str] = [
    TERMINAL_NORTE, TERMINAL_HUB_NORTE, TERMINAL_CENTRAL, TERMINAL_SUR,
]


@dataclass(frozen=True)
class Servicio:
    """
    Un servicio recorre el corredor en ambos sentidos atendiendo un subconjunto de paradas.

    `paradas` son los nombres de estación (en orden norte→sur) en las que se detiene.
    Un servicio expreso omite estaciones para ganar velocidad comercial.

    Las listas de paradas de los expresos son **representativas** (hubs principales sobre
    estaciones reales); las rutas oficiales A/B/C exactas pueden conectarse después sin tocar
    el resto del motor.
    """

    codigo: str
    nombre: str
    paradas: list[str]

    def indices_paradas(self) -> list[int]:
        return [INDICE_ESTACION[p] for p in self.paradas]

    def atiende(self, estacion: str) -> bool:
        return estacion in self.paradas


# Servicio Regular: atiende todas las estaciones (incluye extensiones).
_REGULAR = Servicio(codigo="REG", nombre="Regular", paradas=list(ESTACIONES))

# Expreso A: troncales norte-centro-sur (hubs de mayor demanda).
_EXPRESO_A = Servicio(
    codigo="EXP_A",
    nombre="Expreso A",
    paradas=[
        "Terminal Naranjal", "Independencia", "UNI", "Caquetá", "Tacna",
        "Estación Central", "México", "Javier Prado", "Angamos",
        "Benavides", "Terminal Matellini",
    ],
)

# Expreso B: troncales con énfasis en otro conjunto de hubs.
_EXPRESO_B = Servicio(
    codigo="EXP_B",
    nombre="Expreso B",
    paradas=[
        "Terminal Naranjal", "Izaguirre", "Honorio Delgado", "Estación Central",
        "Canadá", "Canaval y Moreyra", "Angamos", "Ricardo Palma",
        "28 de Julio", "Balta", "Terminal Matellini",
    ],
)

SERVICIOS: list[Servicio] = [_REGULAR, _EXPRESO_A, _EXPRESO_B]
SERVICIOS_POR_CODIGO: dict[str, Servicio] = {s.codigo: s for s in SERVICIOS}


def es_estacion_valida(nombre: str) -> bool:
    """True si `nombre` es una estación conocida del corredor."""
    return nombre in INDICE_ESTACION


def es_terminal(nombre: str) -> bool:
    """True si desde `nombre` se pueden despachar buses."""
    return nombre in TERMINALES


def terminales_de_servicio(servicio: Servicio) -> list[str]:
    """Terminales de despacho que están sobre la ruta del servicio."""
    return [t for t in TERMINALES if t in servicio.paradas]

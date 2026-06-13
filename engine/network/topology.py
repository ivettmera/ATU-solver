"""
Topología del corredor del Metropolitano de Lima.

El corredor es lineal: una secuencia ordenada de estaciones de norte (Naranjal) a sur
(Matellini), con la Estación CENTRAL como nodo intermedio de despacho. Los buses salen de
los dos extremos y de Central. Sobre ese eje circulan varios servicios que saltan paradas
(Regular, Expreso A, Expreso B), igual que en la operación real.

Este módulo es la fuente única de verdad de la red: nombres de estaciones, índices, terminales
de despacho y qué estaciones atiende cada servicio. El resto del `engine/` (trip chaining,
demanda, optimizador) indexa las matrices OD por el orden de `ESTACIONES`.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Estaciones del corredor, ordenadas de NORTE a SUR ────────────────────────────────
# El índice en esta lista es el índice de fila/columna en todas las matrices OD.
ESTACIONES: list[str] = [
    "Naranjal",          # 0  — terminal norte
    "Izaguirre",         # 1
    "Pacifico",          # 2
    "Independencia",     # 3
    "Los Jazmines",      # 4
    "UNI",               # 5
    "Honorio Delgado",   # 6
    "Caqueta",           # 7
    "Tacna",             # 8
    "Jiron de la Union", # 9
    "Colmena",           # 10
    "Estacion Central",  # 11 — nodo CENTRAL de despacho
    "Estadio Nacional",  # 12
    "Mexico",            # 13
    "Canada",            # 14
    "Javier Prado",      # 15
    "Canaval y Moreyra", # 16
    "Aramburu",          # 17
    "Domingo Orue",      # 18
    "Angamos",           # 19
    "Ricardo Palma",     # 20
    "Benavides",         # 21
    "28 de Julio",       # 22
    "Plaza de Flores",   # 23
    "Balta",             # 24
    "Bulevar",           # 25
    "Estadio Union",     # 26
    "Matellini",         # 27 — terminal sur
]

N_ESTACIONES: int = len(ESTACIONES)

# Mapa nombre → índice, para validación y construcción de matrices.
INDICE_ESTACION: dict[str, int] = {nombre: i for i, nombre in enumerate(ESTACIONES)}

# ── Terminales desde donde se despachan buses ────────────────────────────────────────
TERMINAL_NORTE = "Naranjal"
TERMINAL_CENTRAL = "Estacion Central"
TERMINAL_SUR = "Matellini"
TERMINALES: list[str] = [TERMINAL_NORTE, TERMINAL_CENTRAL, TERMINAL_SUR]


@dataclass(frozen=True)
class Servicio:
    """
    Un servicio recorre el corredor en ambos sentidos atendiendo un subconjunto de paradas.

    `paradas` son los nombres de estación (en orden norte→sur) en las que se detiene.
    Un servicio expreso omite estaciones para ganar velocidad comercial.
    """

    codigo: str
    nombre: str
    paradas: list[str]

    def indices_paradas(self) -> list[int]:
        return [INDICE_ESTACION[p] for p in self.paradas]

    def atiende(self, estacion: str) -> bool:
        return estacion in self.paradas


# Servicio Regular: atiende todas las estaciones.
_REGULAR = Servicio(codigo="REG", nombre="Regular", paradas=list(ESTACIONES))

# Expreso A: troncales del norte y centro (salta paradas menores).
_EXPRESO_A = Servicio(
    codigo="EXP_A",
    nombre="Expreso A",
    paradas=[
        "Naranjal", "Independencia", "UNI", "Caqueta", "Tacna",
        "Estacion Central", "Mexico", "Javier Prado", "Angamos",
        "Benavides", "Matellini",
    ],
)

# Expreso B: troncales del centro y sur.
_EXPRESO_B = Servicio(
    codigo="EXP_B",
    nombre="Expreso B",
    paradas=[
        "Naranjal", "Izaguirre", "Honorio Delgado", "Estacion Central",
        "Canada", "Canaval y Moreyra", "Angamos", "Ricardo Palma",
        "28 de Julio", "Balta", "Matellini",
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

# Datos

Recurso de datos del proyecto. **Los archivos de datos no se versionan** (ver `.gitignore`):
solo se conservan la estructura de carpetas y esta documentación.

```
data/
├── raw/         # CSV originales por tarjeta (lo que subes tú, ya limpios)
└── processed/   # artefactos generados (matrices OD, Mbase) — no subir a mano
```

## Qué subir en `data/raw/`

CSV con validaciones **por tarjeta** (un registro por ingreso al torniquete). El Trip Chaining
solo necesita tres campos; nómbralos así o indícame el mapeo si difieren:

| Campo esperado      | Tipo               | Descripción                                  |
|---------------------|--------------------|----------------------------------------------|
| `tarjeta_id`        | texto              | Identificador de la tarjeta/usuario          |
| `timestamp_entrada` | fecha-hora ISO     | Momento del ingreso (ej. `2026-06-13T07:45:00`) |
| `estacion_origen`   | texto              | Estación de ingreso                          |

Notas:
- La **estación de origen** debe poder mapearse a `engine/network/topology.py` (45 estaciones).
  Si los nombres del CSV difieren, el cargador de Fase 6 incluirá una tabla de equivalencias.
- No hay estación de destino (cobro abierto al ingreso): se reconstruye por software.
- Un archivo por día o un archivo con varios días, cualquiera funciona; el cargador agrupa por
  fecha y tipo de día para construir Mbase.

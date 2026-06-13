# Datos

Recurso de datos del proyecto. **Los archivos de datos no se versionan** (ver `.gitignore`):
solo se conservan la estructura de carpetas y esta documentación.

```
data/
├── raw/         # CSV reales por tarjeta (lo que subes tú, ya limpios)
├── sintetico/   # CSV sintéticos para probar el pipeline (scripts/generar_csv_sintetico.py)
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
- La **estación de origen** debe poder mapearse a `engine/network/topology.py` (45 estaciones). El
  cargador (`engine/data_loader.py`) ya normaliza tildes/mayúsculas y acepta `alias_estaciones`
  para nombres que no casen.
- No hay estación de destino (cobro abierto al ingreso): se reconstruye por software (trip chaining).
- Un archivo por día o un archivo con varios días, cualquiera funciona; el cargador agrupa por
  fecha y tipo de día.

## Cómo se procesan

`scripts/seed_baseline.py --csv data/raw` ejecuta todo el pipeline y cachea los artefactos en Redis:

```
CSV por tarjeta  →  data_loader  →  trip chaining (OD por día)  →  Mbase diaria + Mbase intradía
                                                                →  tabla de despacho precalculada
```

No genera archivos en `processed/`: persiste directamente en Redis (`mbase:*`, `mbase:intradia:*`,
`dispatch:tabla`). Para los pasos completos de migración a datos reales ver el **README raíz →
«Migración a datos reales»**.

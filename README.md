# ATU resolver — API de despacho inteligente de buses

API que decide, en tiempo real, el despacho de buses en el corredor del **Metropolitano de
Lima**. El sistema de cobro es abierto al ingreso (los torniquetes solo registran entradas),
por lo que la estación de destino se reconstruye por software.

> **ATU resolver** es el motor de despacho. **Metrohub** es la plataforma que lo consume.

## Pilares matemáticos

1. **Trip Chaining** — reconstruye la matriz Origen-Destino (OD) por continuidad
   espaciotemporal: `destino(i) = origen(i+1)`, con cierre de lazo en el último viaje del día.
2. **Estimación residual** — `M̂(t) = Mbase + ΔM(t)`. `Mbase` (OD esperada por tipo de día) se
   precalcula offline y se cachea en Redis; `ΔM(t)` se estima en vivo con un **Filtro de Kalman**
   sobre CPU. El observado es una ventana móvil, así que Mbase se prorratea a esa ventana para
   comparar en la misma escala.
3. **MILP + Gating** — cada ciclo se evalúa `‖ΔM(t)‖₂`. Si `≤ ε` y sin incidencias, se usa el
   itinerario base (cómputo cero). Si `> ε` o hay incidencia, se ejecuta el solver MILP
   (Google OR-Tools/CBC) bajo restricciones de flota/conductores/headway.

## Estructura

```
app/          Servicio FastAPI (REST + WebSocket), Redis, scheduler periódico
  ├─ api/v1/  Endpoints: telemetry, incidents, dispatch, red (info)
  ├─ core/    config, redis, lifespan, scheduler, caché de Mbase
  ├─ ws/      ConnectionManager (difusión WebSocket)
  └─ static/  dashboard.html (visualización)
engine/       Núcleo matemático puro (sin FastAPI): network/topology, trip_chaining,
              demand (baseline+residual+state), optimizer (gating+milp), data_loader
scripts/      Generadores de datos y seed de Mbase
data/         raw/ (CSV reales por tarjeta) · sintetico/ (CSV de prueba) · processed/
tests/        Pruebas unitarias y de smoke
```

`engine/` no depende de FastAPI ni Redis: recibe estructuras de datos y devuelve resultados.
`app/` orquesta I/O, caché, scheduling y websockets.

## Puesta en marcha

```bash
pip install -r requirements.txt
cp .env.example .env

# 1) Redis (vía docker) + 2) datos sintéticos + 3) Mbase + 4) API
docker compose up -d redis
python scripts/generar_csv_sintetico.py        # CSV por tarjeta en data/sintetico/
python scripts/seed_baseline.py --csv data/sintetico   # construye y cachea Mbase
uvicorn app.main:app --reload

# Alternativa: todo en docker
docker compose up --build
```

- **Dashboard**: http://localhost:8000/  (visualización en vivo)
- **Swagger (API docs)**: http://localhost:8000/docs

## Dashboard

Página única servida por la propia API (sin build ni dependencias externas). Muestra el estado
del sistema (régimen BASE/OPTIMIZADO y `‖ΔM‖₂` vs ε), el plan de despacho (buses por terminal +
tabla), las incidencias activas (crear/resolver) y un control para **simular demanda** y ver
reaccionar al optimizador. Se actualiza por push WebSocket apenas cambia el plan.

## Endpoints

| Método | Ruta | Propósito |
|--------|------|-----------|
| `POST`   | `/api/v1/telemetry/ingress`        | Ingesta de eventos de torniquete (cada ~5 min). |
| `POST`   | `/api/v1/incidents`                | Registrar/refrescar una incidencia (TTL). |
| `GET`    | `/api/v1/incidents`                | Listar incidencias activas. |
| `DELETE` | `/api/v1/incidents/{estacion_id}`  | Resolver una incidencia. |
| `GET`    | `/api/v1/dispatch/recommendations` | Último plan de despacho (pull). |
| `WS`     | `/api/v1/dispatch/stream`          | Empuje proactivo del plan (solo ante cambios). |
| `GET`    | `/api/v1/red/estaciones`           | Estaciones y terminales del corredor. |
| `GET`    | `/api/v1/red/servicios`            | Servicios (Regular / Expreso A / B). |
| `GET`    | `/api/v1/red/config`               | Parámetros operativos (ε, flota, capacidad). |
| `GET`    | `/health`                          | Estado del servicio. |

## Datos

Los CSV no se versionan (ver `.gitignore`); solo la estructura y la documentación (`data/README.md`).

- **`data/raw/`** — CSV reales **por tarjeta** (cuando estén disponibles). Columnas que necesita
  el trip chaining: `tarjeta_id`, `timestamp_entrada`, `estacion_origen`.
- **`data/sintetico/`** — CSV sintéticos en el mismo formato, para probar el pipeline mientras
  llegan los reales (`python scripts/generar_csv_sintetico.py`).

El cargador (`engine/data_loader.py`) admite mapeo de columnas y resolución de nombres de
estación (tolerante a tildes/mayúsculas, con alias), de modo que migrar a datos reales es solo
apuntar el seed a la carpeta nueva:

```bash
python scripts/seed_baseline.py --csv data/raw      # con datos reales
```

## Probar / desarrollar

```bash
pytest                                              # suite completa
python scripts/simulate_telemetry.py --una-vez      # postear telemetría sintética a la API
python scripts/seed_baseline.py --dias 20           # Mbase desde sintético en memoria (sin CSV)
```

## Estado del proyecto

Implementado y verificado end-to-end:

- **Fase 0** — esqueleto navegable + contratos (REST/WS, Redis, scheduler).
- **Fase 1** — Trip Chaining real (OD + cierre de lazo) y generador sintético con ground-truth.
- **Fase 2** — Mbase (promedio OD histórico por tipo de día) y residuo ΔM(t) con Filtro de Kalman.
- **Fase 3** — Topología real (45 estaciones, Chimpu Ocllo↔Matellini, hub Estación Central) y
  optimizador **MILP** (OR-Tools/CBC) con flota/conductores/headway e incidencias.
- **Fase 4** — Push WebSocket proactivo solo ante cambios de plan (+ send-on-connect).
- **Fase 5** — Robustez: Mbase escalada a la ventana, degradación elegante sin telemetría e
  incidencias con ciclo de vida (TTL + crear/listar/resolver).
- **Dashboard** + pipeline de carga desde CSV por tarjeta (listo para datos reales).

Pendiente (**Fase 6**): migración a datos reales por tarjeta cuando estén disponibles
(el pipeline ya está probado con datos sintéticos en el mismo formato).

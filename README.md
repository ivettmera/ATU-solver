# ATU resolver — API de despacho inteligente de buses

API que decide, en tiempo real, el despacho de buses en el corredor del **Metropolitano de
Lima**. El sistema de cobro es abierto al ingreso (los torniquetes solo registran entradas),
por lo que la estación de destino se reconstruye por software.

> **ATU resolver** es el motor de despacho. **Metrohub** es la plataforma que lo consume.

## Pilares matemáticos

1. **Trip Chaining** — reconstruye la matriz Origen-Destino (OD) por continuidad
   espaciotemporal: `destino(i) = origen(i+1)`, con cierre de lazo en el último viaje del día.
2. **Estimación residual** — `M̂(t) = Mbase + ΔM(t)`. `Mbase` se precalcula offline y se cachea en
   Redis **por tipo de día y por hora** (`mbase:intradia:*`, tensor `24×N×N`), de modo que la
   expectativa de la ventana usa el patrón real de la hora (picos) en vez de un prorrateo uniforme;
   `ΔM(t)` se estima en vivo con un **Filtro de Kalman** sobre CPU. Si no hay Mbase intradía sembrada
   se cae al Mbase diario prorrateado (degradación elegante).
3. **MILP + Gating** — cada ciclo se evalúa `‖ΔM(t)‖₂`. Si `≤ ε` y sin incidencias, se sirve el
   **plan precalculado de la hora** desde una tabla por `(tipo_día, hora)` (`dispatch:tabla`, lookup
   O(1)); el plan base ya no es un itinerario fijo sino el plan pico-consciente de esa hora. Si
   `> ε` o hay incidencia, se ejecuta el solver MILP (Google OR-Tools/CBC) bajo restricciones de
   flota/conductores/headway, con objetivo **minimax** (minimiza la peor cola por servicio;
   configurable con `OBJETIVO_DESPACHO`). La tabla se precalcula offline en `seed_baseline.py`.

## Estructura

```
app/          Servicio FastAPI (REST + WebSocket), Redis, scheduler periódico
  ├─ api/v1/  Endpoints: telemetry, incidents, dispatch, red (info)
  ├─ core/    config, redis, lifespan, scheduler, caché de Mbase
  ├─ ws/      ConnectionManager (difusión WebSocket)
  └─ static/  dashboard.html (visualización)
engine/       Núcleo matemático puro (sin FastAPI): network/topology, trip_chaining,
              demand (baseline+residual+state), optimizer (gating+milp), simulation (harness de
              saturación/contingencia), data_loader
scripts/      Generadores de datos y seed de Mbase (diaria + intradía)
data/         raw/ (CSV reales por tarjeta) · sintetico/ (CSV de prueba) · processed/
notebooks/    Cuadernos de exploración (demanda intradía, harness de contingencia)
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

> **Coexistencia con Metrohub**: si Metrohub ya corre en la misma máquina, ocupa el
> puerto **8000** (su backend) y **6379** (Redis). En ese caso levanta ATU en **8001** y
> reutiliza el Redis de Metrohub — no arranques otro. Sustituye `8000` por `8001` en las
> URLs de arriba.

## Apagar y volver a levantar

### Apagar

Detiene solo el proceso de la API de ATU (por puerto, para no tocar otros uvicorn):

```bash
pkill -f "uvicorn app.main:app.*8001"      # usa 8000 si lo levantaste en ese puerto
```

⚠️ **No** apagues el Redis ni un uvicorn que sea de **Metrohub** (su backend en :8000 y su
`metrohub_redis` en :6379). La Mbase queda cacheada en Redis, así que apagar la API no la pierde.

Para confirmar que quedó detenido:

```bash
ss -ltnp | grep ':8001' || echo "apagado"
curl -s http://127.0.0.1:8001/health || echo "sin respuesta"
```

### Volver a levantar

```bash
cd "<ruta-del-proyecto>/ATU-solver"

# 1) Redis arriba (de Metrohub o propio). Si no estuviera:
docker start metrohub_redis        # o:  docker compose up -d redis

# 2) (Solo si Redis se reinició y perdió la Mbase) re-sembrar:
redis-cli KEYS 'mbase:*'                                       # ¿hay Mbase?
.venv/bin/python scripts/seed_baseline.py --csv data/sintetico   # si no la hay

# 3) Levantar la API (8001 para coexistir con Metrohub; 8000 si está libre)
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

- El paso 2 **casi nunca hace falta**: si Redis no se reinició, la Mbase sigue cacheada.
- Para que **no dependa de la terminal** (no se caiga al cerrarla), arráncalo con
  `nohup ... &` o en una pestaña aparte.
- Para un demo que reaccione rápido a la telemetría, antepón `INTERVALO_OPT_SEG=5` al
  comando de uvicorn (por defecto recalcula cada 5 min).

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
apuntar el seed a la carpeta nueva. Un mismo comando reconstruye y cachea **Mbase diaria + Mbase
intradía + tabla de despacho** (ver «Migración a datos reales»):

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
- **Fase 5** — Robustez: degradación elegante sin telemetría e incidencias con ciclo de vida
  (TTL + crear/listar/resolver).
- **Despacho pico-consciente** — Mbase **intradía** (`tipo_día × hora`, tensor `24×N×N`), **tabla de
  despacho precalculada** por `(tipo_día, hora)` servida en O(1) en el caso base, y objetivo MILP
  **minimax** (minimiza la peor cola por servicio). Exploración en `notebooks/01_*`.
- **Harness de simulación** (`engine/simulation/`) — banco de pruebas de colas/saturación que
  inyecta incidentes para validar que el plan base + contingencia evitan el colapso. Ver
  `engine/simulation/README.md` y `notebooks/02_*`.
- **Dashboard** + pipeline de carga desde CSV por tarjeta (listo para datos reales).

Pendiente: **migración a datos reales** por tarjeta cuando estén disponibles (ver abajo; el pipeline
ya está probado con datos sintéticos en el mismo formato).

## Migración a datos reales

Toda la matemática (trip chaining → Mbase diaria/intradía → tabla de despacho → ΔM/MILP) es
**agnóstica a la fuente**: con datos reales **solo cambia el origen de los CSV**. El cargador
(`engine/data_loader.py`) ya resuelve nombres de estación tolerando tildes/mayúsculas y admite
alias y mapeo de columnas, así que normalmente no hace falta tocar código.

1. **Colocar los CSV reales** en `data/raw/` con las columnas `tarjeta_id`, `timestamp_entrada`
   (ISO), `estacion_origen` (una fila por ingreso al torniquete; cobro abierto, sin salida). Ver
   `data/README.md`.
2. **Verificar el mapeo de estaciones** contra `engine/network/topology.py`. Si los nombres del CSV
   difieren y la normalización no basta, pasar `alias_estaciones` / `mapeo_columnas` a
   `cargar_eventos_dir` (o añadirlos en el seed).
3. **Re-sembrar desde los datos reales** — reconstruye Mbase diaria + intradía + la tabla de
   despacho y las cachea en Redis. Nada más cambia:
   ```bash
   .venv/bin/python scripts/seed_baseline.py --csv data/raw
   ```
4. **Recargar la app** (reinicio o próximo arranque): el `lifespan` carga la nueva Mbase y tabla.
   Verificar en logs `Mbase cargada` y `Tabla de despacho precalculada cargada`.
5. **Recalibrar parámetros** con la escala real (en `.env`): `EPSILON` (umbral de gating, depende de
   la magnitud real de `‖ΔM‖₂`), `FLOTA_TOTAL`/`CONDUCTORES_DISPONIBLES`/`CAPACIDAD_BUS`, y, si el
   muestreo es más/menos ruidoso, `q`/`r` del Kalman (`engine/demand/residual.py`).
6. **(Opcional) Validar con el harness**: `PerfilDemanda.desde_mbase_intradia(tensor_real)` corre
   escenarios de saturación/contingencia sobre la demanda real (`engine/simulation/README.md`).

> El generador sintético (`scripts/generar_csv_sintetico.py`) deja de usarse como fuente; queda solo
> para tests y demos. Su limitación conocida (un único pico de mañana) no afecta a los datos reales.

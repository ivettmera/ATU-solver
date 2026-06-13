# MetroSmart — API de despacho inteligente de buses

API que decide, en tiempo real, el despacho de buses en el corredor del **Metropolitano de
Lima**. El sistema de cobro es abierto al ingreso (los torniquetes solo registran entradas),
por lo que la estación de destino se reconstruye por software.

## Pilares matemáticos

1. **Trip Chaining** — reconstruye la matriz Origen-Destino (OD) por continuidad
   espaciotemporal: `destino(i) = origen(i+1)`, con cierre de lazo en el último viaje del día.
2. **Estimación residual** — `M̂(t) = Mbase(día, bloque) + ΔM(t)`. `Mbase` se precalcula
   offline y se cachea en Redis; `ΔM(t)` se estima en vivo con un **Filtro de Kalman** (CPU).
3. **MILP + Gating** — cada 5 min se evalúa `‖ΔM(t)‖₂`. Si `≤ ε` y sin incidencias, se usa el
   itinerario base (cómputo cero). Si `> ε` o hay incidencia, se ejecuta el solver MILP
   (Google OR-Tools) sobre un horizonte deslizante.

## Estructura

```
app/      Servicio FastAPI (REST + WebSocket), Redis, scheduler de 5 min
engine/   Núcleo matemático puro (trip chaining, demanda, optimizador) — sin FastAPI
scripts/  Simulador de telemetría y seed de la línea base
tests/    Pruebas de smoke y unitarias
```

`engine/` no depende de FastAPI ni Redis: recibe estructuras de datos y devuelve resultados.
`app/` orquesta I/O, caché, scheduling y websockets.

## Cómo levantar (desarrollo)

```bash
pip install -r requirements.txt
cp .env.example .env

# Opción A: Redis vía docker, API local
docker compose up -d redis
uvicorn app.main:app --reload

# Opción B: todo en docker
docker compose up --build
```

Documentación interactiva (Swagger): http://localhost:8000/docs

## Endpoints (`/api/v1`)

| Método | Ruta | Propósito |
|--------|------|-----------|
| `POST` | `/telemetry/ingress` | Ingesta de eventos de torniquete (cada 5 min). |
| `POST` | `/incidents` | Registrar bloqueos/accidentes que modifican el optimizador. |
| `GET`  | `/dispatch/recommendations` | Último plan de despacho óptimo (pull). |
| `WS`   | `/dispatch/stream` | Empuje proactivo de decisiones a las apps cliente. |

## Probar el flujo

```bash
python scripts/seed_baseline.py        # carga Mbase inicial en Redis
python scripts/simulate_telemetry.py   # postea telemetría sintética cada 5 min
pytest                                  # pruebas
```

## Estado del proyecto

Entrega 1 (Fase 0): **esqueleto navegable + contratos**. Los endpoints responden con datos
mock; la matemática real (trip chaining, Mbase+ΔM, MILP) se implementa en las fases siguientes.
El plan completo está en el plan de desarrollo del equipo.

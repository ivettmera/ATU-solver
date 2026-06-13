# Cuadernos de exploración — ATU resolver

Cuadernos de **investigación** (no son parte del servicio). Aquí se prototipa y se mide antes de
tocar `engine/`+`app/`. El motor en producción permanece intacto; estos cuadernos solo **importan**
sus funciones y miden ideas nuevas.

## Cuadernos

- **`01_exploracion_demanda_intradia.ipynb`** — Demanda intradía y despacho precalculado.
  Demuestra que el `Mbase` promedio-diario aplana los picos horarios, construye un `Mbase` por hora
  (`tipo_día → 24×N×N`), precalcula una **tabla de despacho** por `(tipo_día, hora)` resoluble en
  O(1) en runtime, y prototipa un objetivo **minimax** (minimizar la peor cola por servicio) frente
  al objetivo de suma actual. Cierra con una propuesta de integración al motor — **ya integrada en
  producción** (Mbase intradía, tabla de despacho precalculada y objetivo minimax; ver README raíz).

- **`02_harness_contingencia.ipynb`** — Demo del harness de simulación (`engine/simulation`).
  Simula colas y saturación por estación bajo un plan de despacho, inyecta una disrupción en un hub
  (que **colapsa** la red bajo el plan base) y muestra la **recuperación** con un re-plan de
  contingencia. Ver `engine/simulation/README.md` para las decisiones de diseño.

## Cómo correrlos

```bash
# Desde la raíz del repo, con el venv del proyecto:
.venv/bin/pip install -r requirements-notebook.txt

# Datos sintéticos por tarjeta (60 días → suficientes laborales/sábados/domingos por hora):
.venv/bin/python scripts/generar_csv_sintetico.py --dias 60 --inicio 2026-04-01

# Opción A — interactivo:
.venv/bin/jupyter notebook notebooks/

# Opción B — ejecutar de punta a punta sin abrir UI:
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
  notebooks/01_exploracion_demanda_intradia.ipynb
```

Los cuadernos se ejecutan desde la raíz del repo (resuelven los imports de `engine/` por sí
mismos). Los CSV de `data/` no se versionan; regéneralos con el comando de arriba.

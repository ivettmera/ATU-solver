# `engine/simulation` — Harness de saturación y contingencia

Simulador estocástico *time-stepped state-space* del corredor del Metropolitano. Su único fin es
**validar decisiones de despacho**: comprobar que un plan mantiene las estaciones bajo control en un
día normal y que un re-plan de contingencia **evita el colapso** cuando ocurre un incidente.

> Es un **banco de pruebas**, no un servicio ni una fuente de datos de entrenamiento de ML.
> El motor de producción (`app/` + resto de `engine/`) no depende de este módulo.

---

## Decisiones de diseño y su justificación

### 1. La demanda normal se modela con **matemática simple**, no con ML
**Decisión.** El patrón del día normal se captura con un **perfil estacional** (Mbase intradía por
tipo de día y hora) + calendario (feriado/escolar) + tendencia lenta (EWMA) + el **Filtro de Kalman
ya existente** para el residuo en vivo. El ML queda para una **2ª fase acotada** (nowcasting a
30–60 min o picos exógenos) y solo si los datos reales muestran estructura que el perfil no capta.

**Por qué.**
- La demanda es un **patrón periódico estable** (estudiantes/trabajadores, picos repetidos todo el
  año). En ese régimen, el mejor predictor es el **promedio condicional histórico** indexado por
  `(tipo_día, hora, calendario)`: O(1), interpretable y exacto sobre lo estable. Un ML aporta solo
  una mejora marginal a cambio de mucha complejidad e iteración lenta.
- La restricción de **recuperación rápida ante incidentes** empuja en contra del ML online: un
  incidente no es un problema de *predicción* sino de *re-optimización* ante un cambio súbito de
  capacidad. Eso se resuelve mejor con **optimización (MILP) + caché/precálculo + warm-start**, que
  además respeta restricciones duras y es explicable frente a un operador.
- Los incidentes son **raros y heterogéneos** → pocos datos para entrenar una política; el MILP da
  decisiones óptimas por escenario con garantías.

### 2. El simulador es un **harness de contingencia/saturación**, no un generador para ML
**Decisión.** Construir un simulador state-space que produce **colas y % de saturación por estación
y bloque**, e inyecta incidentes, para **probar** el plan base y el de contingencia.

**Por qué.** En el sistema real el cobro es **abierto al ingreso**: solo se observan **entradas**.
La **cola y la saturación son latentes** —no se pueden medir con los datos reales—. Sin un
simulador no hay forma de cuantificar "espera/saturación" ni de validar que la contingencia evita
el colapso. Ese, y no el entrenamiento de un modelo, es el valor del simulador.

### 3. Modelo **agregado por bloques de tiempo**, no agente-por-agente (ABM)
**Decisión.** Estado por estación en pasos `Δt = 5 min` (consolidado a hora), con llegadas
`X_s,t ~ Poisson(λ_s,t)`, destinos `~ Multinomial(X, P_s)` desde una OD por bloque, y despeje
`E_s,t = min(Q_{s,t-1} + X_s,t, capacidad_t)`. Saturación `= Q_s,t / aforo_s`.

**Por qué.** Para medir **saturación por estación** un modelo agregado es más eficiente y escalable
que simular agente por agente; el ABM solo se justifica si se necesita micro-comportamiento, que
aquí no aporta a la decisión de despacho.

### 4. El **plan de despacho es la variable de control** (somos administradores)
**Decisión.** El throughput por estación no es un dato fijo: se **deriva del `DispatchPlan`**
(`plan_a_capacidad_por_estacion`) usando los patrones de parada de `topology` y el headway. El
admin decide trayectorias y frecuencias en todo momento.

**Por qué.** Así el harness cierra el lazo con el optimizador: se le entrega un plan (precalculado o
de contingencia) y responde con la saturación resultante. La "inyección de flota" es, simplemente,
cambiar el plan.

### 5. Se **conserva** el generador actual; el harness **coexiste**
**Decisión.** `engine/trip_chaining/synthetic.py` y `scripts/generar_csv_sintetico.py` quedan
intactos; el harness es un módulo nuevo y aditivo.

**Por qué.** El generador actual cumple otro rol (validar trip chaining; alimentar el seed de
Mbase) y de su contrato dependen `tests/test_trip_chaining.py` y `historico.construir_mbase_sintetico`.
No cumple esta arquitectura (sin estado, sin colas, sin Poisson, destinos uniformes, pico único) y
**no debe** forzarse a hacerlo.

### 6. **Listo para datos reales** desde el diseño
**Decisión.** El harness consume un `PerfilDemanda` (`λ[s,bloque]` + OD por bloque). Hoy se
construye paramétricamente (`PerfilDemanda.sintetico`, con direccionalidad mañana→centro /
tarde→periferia y picos bimodales AM/PM); cuando lleguen los CSV reales se construye del **mismo
tensor Mbase intradía** (`desde_mbase_intradia`) sin tocar el resto del motor.

**Por qué.** Pronto habrá validaciones reales por tarjeta. Aislar la **fuente** del perfil detrás de
un constructor permite migrar cambiando solo el origen de los datos.

### Sobre el trip chaining
Se mantiene como estimador de **destino/carga** (necesario para asignar Regular vs. Expreso y la
carga entre estaciones), pero **no** se le apuesta la solución de saturación: la señal primaria de
cola son los **ingresos observados** por estación/hora, que no requieren reconstrucción. El chaining
añade una dimensión útil con **error de supuesto** (cierre de lazo), a validar con datos reales.

---

## Componentes

| Archivo | Rol |
|---|---|
| `config.py` | `RedConfig`: aforo por estación (por rol terminal/hub/regular) y capacidad/headway por servicio. Parámetros del administrador. |
| `demanda_perfil.py` | `PerfilDemanda`: `λ` y OD por bloque. Constructores `sintetico(...)` y `desde_mbase_intradia(...)`. |
| `engine.py` | `simulate_step(state, t, modifiers)` y `simular_dia(perfil, plan, config, modifiers, dt_min=5)`. |
| `plan_capacidad.py` | `plan_a_capacidad_por_estacion(plan, config)`: traduce el `DispatchPlan` a throughput por estación/bloque. |
| `incidentes.py` | `inject_transit_disruption(...)` (con represamiento aguas-arriba) e `inject_external_event(...)` (pico de λ exógeno). |
| `metricas.py` | Línea de tiempo de saturación, cola pico por estación, pasajeros·hora de espera, bandera de colapso. |

Reutiliza `engine/network/topology.py`, `engine/optimizer/dispatch_plan.py` y
`engine/optimizer/milp.py`. Demo en `notebooks/02_harness_contingencia.ipynb`.

## Migración a datos reales
Cuando lleguen los CSV reales por tarjeta, el harness aplica directamente sobre la demanda real:
construye el tensor Mbase intradía con el pipeline de producción y aliméntalo con
`PerfilDemanda.desde_mbase_intradia(tensor_24xNxN)`. El resto (incidentes, métricas, simulación) no
cambia. Los pasos completos están en el **README raíz → «Migración a datos reales»**.

## Fuera de alcance
- Integración del baseline estacional en producción (track "matemática simple" de la demanda).
- Cualquier modelo de ML (2ª fase, solo si los datos reales lo justifican).
- Propagación mesoscópica de buses entre estaciones (tiempos de viaje): v1 usa colas por estación
  con backpressure simple.

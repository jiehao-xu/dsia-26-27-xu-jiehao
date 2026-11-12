# Madrid Air

Madrid Air estima la concentración media diaria de NO₂ en Escuelas Aguirre,
Madrid, para los próximos 30 días. La idea es comprobar hasta dónde podemos
anticipar la contaminación a partir de su histórico y del calendario.

Utiliza CSV y Pandas para trabajar con los datos, un Random Forest de
scikit-learn para predecir y Gemini para explicar los resultados. Python calcula
las predicciones y los errores; Gemini recibe esas cifras y redacta una
explicación para cada fecha.

## Cómo ponerlo en marcha

Los comandos siguientes se ejecutan desde `proyecto_ii`, con su entorno virtual
activado. `--active` indica a uv que use ese entorno. El archivo `uv.lock` está
en la raíz del repositorio porque el proyecto comparte el workspace.

```bash
uv sync --active --locked --package madrid-air --group dev
```

Si todavía no tienes `.env`, copia `.env.example` con ese nombre. Si ya existe,
edítalo sin reemplazar tus claves. Para interpretar los resultados necesitas:

```dotenv
AI_PROVIDER=google
GOOGLE_API_KEY=tu_clave
GOOGLE_MODEL=gemini-3.1-flash-lite
```

Después ejecuta:

```bash
uv run --active --package madrid-air madrid-air forecast
```

El comando actualiza NO₂ y calendario desde enero de 2023, evalúa el modelo en
fechas pasadas, lo entrena con el histórico disponible y genera el pronóstico.
Al terminar, hace una llamada a Gemini para explicar todas las filas.
Este flujo diario no necesita la clave de AEMET.

Para probar sin llamar a Gemini, añade `--ai-mode mock`. Se generará un texto
de prueba identificado como tal; las descargas y el entrenamiento siguen siendo
reales. `forecast` y `forecast-analyze` usan la API por defecto, aunque `.env`
contenga `AI_MODE=mock` para los comandos horarios.

Si prefieres el entorno compartido de la raíz, omite `--active`. Como alternativa
a uv, desde la raíz puedes ejecutar `python -m pip install -r proyecto_ii/requirements.txt`
y después `python -m pip install --no-deps -e proyecto_ii`.

## Dónde ver los resultados

Abre **`data/final/forecast_report.md`**. Incluye todas las predicciones, sus
explicaciones y un resumen de la evaluación. En VS Code puedes verlo formateado
con `Ctrl + Shift + V`.

| Archivo en `data/final/` | Qué contiene |
| --- | --- |
| `forecast.csv` | Predicciones, contexto por fecha y explicación de Gemini. |
| `forecast.png` | Gráfico del histórico reciente y las predicciones. |
| `daily_dataset.csv` | Medias diarias de NO₂ y cobertura de horas válidas. |
| `daily_backtest.csv` | Predicciones sobre fechas pasadas y sus valores reales. |
| `daily_metrics.csv` | Errores del modelo y de las referencias para cada horizonte. |
| `forecast_summary.md` | Resumen numérico local, disponible sin Gemini. |
| `forecast_metadata.json` | Fechas, retraso de los datos y cortes de evaluación. |
| `forecast_interpretation.json` | Respuesta de la API y datos enviados para revisarla. |

Para generar otra interpretación sin descargar ni entrenar de nuevo:

```bash
uv run --active --package madrid-air madrid-air forecast-analyze
```

## Cómo se construye el pronóstico

Primero se agrupan las medidas horarias por día de Madrid. Solo se acepta una
media diaria cuando hay al menos un 75 % de horas válidas. Los días de cambio
horario pueden tener 23 o 25 horas; el cálculo lo tiene en cuenta. Los días sin
suficientes datos quedan vacíos y el día actual se excluye porque aún no ha terminado.

Cada modelo aprende a predecir a una distancia concreta desde la última
observación. Utiliza NO₂ reciente, valores de días anteriores, medias móviles
y el calendario de la fecha objetivo. No necesita suponer qué tráfico o qué
meteorología habrá dentro de varias semanas.

Para evaluar, se simulan pronósticos desde distintas fechas del pasado. En cada
una se entrena solo con objetivos fechados como máximo en el corte. El relleno
de variables se aprende con ese entrenamiento; las concentraciones objetivo
que faltan nunca se rellenan. Después se entrenan los modelos finales con todo
el histórico etiquetado disponible y se guardan en `models/daily_random_forests.joblib`.

Por defecto se evalúan tres ventanas. Para ampliar la comprobación:

```bash
uv run --active --package madrid-air madrid-air forecast --folds 12
```

`--days` cambia el número de fechas futuras, entre 1 y 90. `--start` fija el
inicio del histórico y `--end AAAA-MM-DD` la fecha de emisión, que por defecto
es hoy. El informe conserva esas fechas para distinguir una ejecución antigua
de un pronóstico actual.

## Qué dicen los resultados actuales

En la ejecución del 12 de noviembre de 2026 había 1.354 días con cobertura
suficiente desde enero de 2023. La última observación era del 30 de septiembre:
un retraso de 43 días. Por eso las fechas futuras estaban a entre 44 y 73 días
del último dato, aunque el informe mostrara los siguientes 30 días del calendario.

La evaluación utilizó 12 cortes entre agosto de 2025 y julio de 2026:

| Método | MAE (µg/m³) |
| --- | ---: |
| Random Forest | 9,60 |
| Repetir la última semana observada | 9,34 |
| Mantener el último valor observado | 10,85 |

El MAE es el error absoluto medio: cuanto menor, mejor. En esta evaluación el
bosque mejora mantener el último valor, pero **no supera repetir la última semana**.
El RMSE, también incluido en los CSV, da más peso a los errores grandes.

Estos errores no son un margen garantizado para cada fecha futura. Además,
los archivos históricos pueden contener revisiones posteriores: la evaluación
no reconstruye exactamente qué datos estaban publicados en cada momento.
Si el último dato tiene más de 90 días de retraso, el programa pide actualizarlo.

## Qué aporta Gemini

Gemini recibe la predicción, el calendario, las diferencias frente a la
referencia y al día anterior, y el error histórico del horizonte con su número
de casos. Python calcula las diferencias antes de enviarlas. Se pide una
explicación de 45 a 75 palabras por fecha y un resumen global, en una sola llamada.

El cliente usa la API REST
[`generateContent`](https://ai.google.dev/api/generate-content), con la clave
en una cabecera y un tiempo de espera de 60 segundos. El modelo se cambia con
`GOOGLE_MODEL`; su acceso y coste dependen de la cuenta. El límite de salida
diario es de 700 + 220 tokens por fecha y no hay reintentos automáticos.

Antes de guardar se comprueba que haya una explicación para cada fecha, sin
duplicados ni textos vacíos. Esto valida la estructura, pero no garantiza que
el texto sea correcto. Por ejemplo, ser lunes no demuestra que una subida se
deba al tráfico. Las explicaciones deben contrastarse con las cifras.

Si falla la API, el programa muestra el error y conserva los resultados
numéricos. No hace pasar una plantilla por una respuesta real. Puedes repetir
solo `forecast-analyze` cuando vuelva a estar disponible el servicio.

## De dónde salen los datos

El pronóstico diario utiliza estas dos fuentes municipales:

- [Calidad del aire](https://datos.madrid.es/dataset/201200-0-calidad-aire-horario):
  estación 28079008, Escuelas Aguirre, magnitud 8 (NO₂). Se conservan las medidas
  no negativas marcadas como válidas; el resto queda como ausente.
- [Calendario laboral](https://datos.madrid.es/dataset/300082-0-calendario_laboral):
  clasificación de festivos y días laborables. Si faltan fechas necesarias,
  el programa lo indica en lugar de inventarlas.

El flujo horario anterior también incorpora
[AEMET OpenData](https://opendata.aemet.es/dist/), con datos diarios de Madrid
Retiro (`3195`), el
[histórico de tráfico](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico)
y la [ubicación de sensores](https://datos.madrid.es/dataset/202468-0-intensidad-trafico).
Se descartan las medidas de tráfico inválidas y se seleccionan sensores próximos
a la estación, con un radio de 500 metros por defecto.

Fuente de los datos municipales: Ayuntamiento de Madrid, bajo la licencia
indicada en su catálogo (CC BY 4.0). Fuente meteorológica: AEMET OpenData.

Las descargas originales se guardan en `data/raw/`; las tablas limpias, en
`data/processed/`. Se reutilizan las descargas históricas y se revisan las
particiones recientes, con una ventana de 14 días configurable mediante
`--overlap-days`. El recurso acumulado de NO₂ desde 2025 y el calendario se
descargan completos cuando corresponde actualizarlos.

Si llega una corrección, sustituye el registro con la misma clave. Cada CSV
se escribe primero en un temporal para conservar el anterior si falla la
escritura. No hay una transacción conjunta para todos los archivos: evita
ejecutar dos actualizaciones a la vez sobre la misma carpeta.

## Si algo falla

| Situación | Qué hacer |
| --- | --- |
| Aviso de que el entorno virtual no coincide | Usa `--active` con el entorno de `proyecto_ii` activado. |
| Error de certificado de la fuente | Revisa el proveedor, la red o la VPN. No desactives la verificación SSL. |
| No puedes descargar, pero ya tienes los CSV | Ejecuta `forecast --offline`. Sigue llamando a Gemini salvo que añadas `--ai-mode mock`. |
| Falta la clave de Google | Completa `GOOGLE_API_KEY` en `.env` o usa mock para probar. |
| La API falla después de entrenar | Repite `forecast-analyze`; no necesitas entrenar otra vez. |

`--offline` no sirve en una instalación sin datos. Tampoco convierte datos
antiguos en recientes: comprueba siempre la última observación del informe.

## Código y pruebas

Para seguir el flujo diario, empieza por `processing/daily.py`, continúa por
`ml/daily_forecast.py` y termina en `ai/daily_report.py`. Las descargas están en
`ingestion/`, las funciones de escritura en `storage.py` y los comandos en `cli.py`.

Desde `proyecto_ii`:

```bash
uv run --active --package madrid-air pytest tests -q
```

En la última comprobación pasaron 46 pruebas. Cubren limpieza, cambios de hora,
actualizaciones, escritura fallida, carga e inferencia del modelo, evaluación
temporal y respuestas incompletas de la API. Usan datos sintéticos y peticiones
simuladas; las conexiones de red están bloqueadas durante los tests.

El [workflow de CI](../.github/workflows/proyecto-ii.yml) instala las dependencias
del lock y ejecuta esas pruebas sin claves. Aún queda comprobar su ejecución en
GitHub y repetir la instalación desde un clon limpio.

## Comandos del flujo horario anterior

La primera versión predecía solo la siguiente hora y sigue disponible. Estos
comandos no generan el informe diario:

| Comando | Función |
| --- | --- |
| `update` | Descarga y limpia las fuentes; `--sources` permite elegirlas. |
| `build` | Combina los CSV y crea `dataset.csv` y `coverage.csv`. |
| `train` | Evalúa y guarda el modelo horario en `random_forest.joblib`. |
| `predict` | Predice la siguiente hora y guarda `predictions.csv`. |
| `analyze` | Predice e interpreta esa hora; guarda `analysis.csv`. |
| `run` | Ejecuta el flujo completo; `--retrain` vuelve a entrenar. |

Para probarlo, configura `AEMET_API_KEY` y empieza por un mes, porque el tráfico
de varios años puede ocupar varios GB:

```bash
uv run --active --package madrid-air madrid-air run --start 2023-01-01 --end 2023-01-31 --ai-mode mock
```

Las horas se guardan en UTC y se usa el calendario local de Madrid. Las horas
ambiguas de los cambios de horario se dejan como huecos. AEMET aporta resúmenes
diarios, que se retrasan siete días por defecto (`AEMET_LAG_DAYS`); ese retraso
es una hipótesis de disponibilidad, no una garantía. El modelo horario reserva
el 20 % más reciente para evaluar y excluye los ejemplos de entrenamiento cuyo
objetivo alcance el test. A diferencia del modelo diario, conserva ese modelo
evaluado sin reajustarlo con el test.

## Entrega y siguientes pasos

El repositorio conserva el código, tests, configuración de ejemplo e instrucciones
para regenerar datos y modelos. `.env`, entornos, descargas y resultados quedan
fuera de Git. El uso de IA durante el desarrollo se explica en
[AI_USAGE.md](AI_USAGE.md).

Antes de entregar quedan pendientes publicar los cambios, comprobar CI y
reproducir el proyecto desde un clon limpio. Para el Proyecto III, la idea es
añadir una API o interfaz para consultar las predicciones, desplegarla y vigilar
la actualización de los datos y el error del modelo.

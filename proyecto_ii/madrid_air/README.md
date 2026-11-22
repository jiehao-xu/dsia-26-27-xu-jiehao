# NO₂ Madrid

Proyecto II — Automatización e integración de servicios. El objetivo es predecir
la **concentración media diaria de NO₂ de la red municipal de Madrid**, en µg/m³,
para el siguiente día del histórico disponible.

La referencia municipal es la media aritmética de las mediciones válidas de las
estaciones de calidad del aire. Cada estación pesa igual: no es una media
ponderada por superficie o población ni la concentración de cada barrio.

## Ejecutar

Python 3.12 o superior y uv, desde esta carpeta:

```powershell
uv sync --locked --package no2-madrid --group dev
uv run no2-madrid run --ai-mode real
```

`run` reconstruye el dataset si es necesario, carga el modelo ya entrenado,
predice y solicita un resumen a Gemini. No descarga ni reentrena. La agregación
de tráfico usa una caché diaria; la primera pasada puede tardar varios minutos.

La salida JSON contiene `scope: Madrid`, el valor previsto, la definición del
objetivo, los IDs y número de estaciones de la red, la cobertura de NO₂ del día
de referencia, las fechas límite de información, el error histórico y el resumen.
Se guarda en `reports/runs/prediction_AAAA-MM-DD.json`.

## Reproducibilidad sin claves ni descargas

```powershell
uv run no2-madrid demo --dir artifacts/demo
uv run pytest -q
```

La demostración genera dos estaciones sintéticas y predice su media con IA en
`mock`; no lee `.env`. Sus resultados quedan separados en `artifacts/demo/` y
no representan métricas sobre los datos reales de Madrid.

Sin uv: instalar `requirements.txt`, ejecutar `python -m pip install --no-deps -e .`
y utilizar `python -m no2_madrid` como alternativa al comando instalado.

## Preparar los datos y entrenar

Crear `.env` a partir de `.env.example` si aún no existe. Las claves se guardan
solo en `.env`, excluido de Git. Las fuentes municipales no necesitan clave.

```powershell
# Si faltan datos: descarga por años para NO₂/meteorología y por meses para tráfico.
uv run no2-madrid ingest --source all --start 2023-01-01 --end 2026-10-31
uv run no2-madrid preprocess --workers 1

# Si ya tienes los archivos limpios: empezar aquí.
uv run no2-madrid build-dataset
uv run no2-madrid train --train-end 2024-12-31 --validation-end 2025-12-31
uv run no2-madrid predict --ai-mode mock
```

La descarga completa de tráfico ocupa muchos GB. `ingest --source` admite
`no2`, `municipal`, `calendar`, `traffic`, `metadata` y `all`; los catálogos de
coordenadas sirven como referencia, no son necesarios para filtrar por radio.
`--refresh` actualiza los ZIP de tráfico. La limpieza omite meses sin cambios.
`run --prepare` incluye limpieza; no se programan tareas externas automáticamente.

Opciones globales, antes del subcomando:

```powershell
uv run no2-madrid --data-dir data --output-dir . build-dataset
```

## Configuración y objetivo municipal

- `MIN_STATION_COVERAGE=0.75`: se exige un 75 % de estaciones con NO₂ válido.
- `METEO_LAG_DAYS=7`: retraso supuesto para la meteorología municipal.
- `NO2_LAG_DAYS=1` y `TRAFFIC_LAG_DAYS=1`: retrasos supuestos del resto de observaciones.
- `USE_TRAFFIC=true`: incorporar la red de tráfico procesada; `false` debe mantenerse en dataset, entrenamiento e inferencia.
- `AI_MODE=mock` o `real`, `AI_PROVIDER=google`, `GOOGLE_API_KEY` y `GOOGLE_MODEL`.

La red objetivo se identifica mediante las estaciones presentes en el histórico
limpio y se registra en el dataset y el modelo. Con los 24 identificadores del
histórico actual se necesitan al menos 18 mediciones válidas para formar la
media. Los días por debajo del umbral quedan sin objetivo: no se imputan.
Un cambio en la composición de la red requiere reentrenar.

La configuración anterior de una estación individual y un radio de 500 metros
se ha retirado. El modelo actual debe entrenarse desde cero con las medias de
Madrid; cambiar la etiqueta de salida del modelo anterior no sería válido.

## Fuentes, motivación y atribución

Todas las fuentes observadas proceden del **Ayuntamiento de Madrid, portal
Datos Abiertos**. El histórico de NO₂ aporta el objetivo; la meteorología,
el tráfico y el calendario son variables candidatas cuya utilidad se evalúa
comparando modelos, sin suponer relaciones causales.

| Fuente | Acceso |
|---|---|
| NO₂ diario | [Calidad del aire diaria](https://datos.madrid.es/dataset/201410-0-calidad-aire-diario) |
| Meteorología horaria | [Meteorología municipal desde 2019](https://datos.madrid.es/dataset/300352-0-meteorologicos-horarios) |
| Tráfico histórico | [Puntos de medida históricos](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico) |
| Calendario | [Calendario laboral de Madrid](https://datos.madrid.es/dataset/300082-0-calendario_laboral) |
| Estaciones de calidad del aire | [Catálogo municipal](https://datos.madrid.es/dataset/212629-0-estaciones-control-aire) |
| Sensores de tráfico | [Ubicación de puntos de medida](https://datos.madrid.es/dataset/202468-0-intensidad-trafico) |

Atribución: Ayuntamiento de Madrid. Los datos se limpian y agregan en este
proyecto. Consultar las condiciones de reutilización de cada ficha; las de
meteorología, calendario y ubicación de tráfico indican CC BY 4.0. Los catálogos
registran las URL exactas descargadas en `data/metadata/sources.json`.

## Preparación de variables y disponibilidad

| Fuente | Transformación |
|---|---|
| NO₂ | Media diaria entre estaciones válidas, número de mediciones y cobertura; umbral configurable. |
| Meteorología | Agregación diaria por estación y parámetro con al menos 18 horas válidas; después media entre estaciones. Temperaturas mínima/máxima son medias de los extremos de cada estación. Se omite dirección del viento. |
| Tráfico | Media de intervalos por sensor y día y después media entre sensores de toda la red; agregados adicionales separados para URB y C30, sensores disponibles y número de intervalos. |
| Calendario | Día de semana, mes cíclico, fin de semana y festivo; los festivos desconocidos quedan ausentes. |

No se convierten intensidades en totales de vehículos ni el número de muestras
en duración. La cobertura de sensores puede cambiar y debe revisarse; no se
asume un panel de tráfico constante ni se afirma que la media de sensores
represente la cantidad total de circulación de la ciudad.

Se usan retardos de NO₂, media y desviación de los siete días anteriores, y
observaciones meteorológicas/de tráfico con sus retrasos configurados. Los
retardos se calculan sobre un calendario diario completo para respetar huecos.
No se utilizan observaciones del propio día objetivo. La imputación de entradas
se aprende solo con entrenamiento; el objetivo no se imputa.

Los retrasos son hipótesis de simulación, no garantías de publicación. Los
históricos municipales pueden publicarse después: esta entrega realiza una
evaluación histórica secuencial. La fecha automática es el siguiente día del
NO₂ disponible, no necesariamente mañana respecto a la ejecución.

## Entrenamiento y evaluación

Se comparan persistencia, Ridge con NO₂/calendario, Ridge con todas las variables
y HistGradientBoostingRegressor con todas las variables. Los modelos incluyen
imputación por mediana, indicadores de ausencia y escalado en una Pipeline
sklearn. Se selecciona por MAE de validación y después se ajusta el ganador con
entrenamiento y validación; test permanece reservado. La persistencia también
puede ganar y se guarda como regresor sklearn.

| Periodo | Uso |
|---|---|
| 2023–2024 | Entrenamiento de candidatos |
| 2025 | Validación y selección |
| 2026 disponible | Test final secuencial |

Solo se evalúan días con objetivo válido y NO₂ de referencia disponible.
El MAE y RMSE se expresan en µg/m³. Se informa del error mensual, de los días
de concentración alta y de las ausencias por partición. El MAE no es un
intervalo de confianza. Se limitan a cero las predicciones negativas.

Métricas actuales: `reports/evaluation.md` y `reports/metrics.json`.

Ejecución municipal verificada el 22 de noviembre de 2026: red de 24 estaciones, 1.368 objetivos diarios válidos y modelo ridge_basic. MAE de test: 5,160 µg/m³; RMSE: 6,830 µg/m³, sobre 304 días. La predicción histórica para el 1/11/2026 es 30,16 µg/m³. Gemini respondió HTTP 200 con ai_status=real. Estos resultados corresponden a la media de Madrid.
Las cifras del modelo anterior de una sola estación no son las métricas de
Madrid. Su evidencia se conserva etiquetada en `reports/archive/station_4/`.
El tráfico procesado disponible termina en octubre de 2025; los meses
posteriores siguen pendientes de limpieza y sus entradas en test quedan
ausentes. Esta limitación no afecta a la definición municipal del objetivo.

## Artefactos y estructura

| Ubicación | Contenido |
|---|---|
| `src/no2_madrid/` | Ingesta, limpieza, dataset, variables, entrenamiento, predicción, CLI y clientes de IA |
| `data/raw/` | Originales descargados |
| `data/process/` | CSV limpios por fuente; meteorología en `meteorologia_municipal/` |
| `data/dataset/` | Dataset diario, informe de cobertura y caché de tráfico |
| `data/metadata/` | Catálogos municipales de referencia |
| `artifacts/model.joblib` y `.json` | Modelo, contrato municipal, estaciones, variables, fechas, versiones y SHA-256 del dataset de entrenamiento |
| `reports/` | Métricas, predicciones de test, informe, gráficos y ejecuciones |
| `tests/` | Pruebas unitarias e integración |

Datos voluminosos, modelos binarios y ejecuciones quedan fuera de Git; se
entregan instrucciones para reentrenar y dependencias bloqueadas en el `uv.lock` de la raíz del repositorio, compartido por el workspace.
Solo cargar artefactos joblib propios y fiables. Los modelos anteriores de una
estación son incompatibles con el nuevo contrato municipal y no se reutilizan.

## Interpretación con Gemini

Proveedor: Google Gemini API mediante `google-genai`; tarea: generar un resumen
breve en español del valor calculado por sklearn. Modelo configurable en
`GOOGLE_MODEL`, por defecto `gemini-3.1-flash-lite`. Se envían fecha, ámbito
Madrid, número de estaciones, predicción, ausencias y MAE histórico.

`mock` no usa red ni claves. En modo `real` se utilizan tiempo límite de 20
segundos y dos intentos configurados en el SDK. Si falla, se conserva el valor
numérico y se devuelve una plantilla con `ai_status=fallback`. La prosa no debe
atribuir causas ni dar recomendaciones sanitarias; puede contener errores y no
modifica el resultado numérico. No se registran claves ni mensajes de error
del proveedor que puedan contener credenciales.

Referencia: [SDK oficial de Google](https://github.com/googleapis/python-genai).
Uso de IA durante el desarrollo: [AI_USAGE.md](AI_USAGE.md).

## Pruebas y continuidad

Las pruebas cubren limpieza, media municipal, cobertura mínima, agregación
entre estaciones, tráfico independiente del tamaño de bloque, retardos y
ausencia de información futura, persistencia/carga/inferencia del modelo,
cliente Google simulado y alternativa ante errores. La integración utiliza
varias estaciones sintéticas y comprueba `scope: Madrid`.

La CI está definida en `.github/workflows/proyecto-ii.yml` de la raíz del repositorio. Ejecuta los comandos desde `proyecto_ii/madrid_air`, instala el paquete `no2-madrid` con el lockfile compartido, ejecuta pytest y una demostración con IA en `mock`, sin claves. 
El Proyecto III podrá reutilizar las funciones para
añadir API/app, despliegue y monitorización.

## Mejoras futuras: predicciones diarias y mensuales

Ampliar el horizonte de predicción de NO₂ en Madrid con dos funcionalidades:

- **Pronóstico diario para los próximos 7 o 30 días:** generar una estimación para cada fecha, incluyendo la posibilidad de mostrar un mes completo con sus valores diarios.
- **Predicción de la media mensual:** estimar un único valor de concentración media de NO₂ para el conjunto del mes.

Estas funcionalidades requieren adaptar el entrenamiento para cada horizonte y
resolver la disponibilidad de las entradas futuras de meteorología y tráfico,
utilizando pronósticos o modelos que no dependan de observaciones futuras.
La evaluación deberá respetar el orden temporal, comparar con referencias
sencillas y medir el error por horizonte. También se propone incorporar
intervalos de predicción cuya cobertura se compruebe con datos reservados.

El modelo actual predice el siguiente día del histórico disponible; estas
ampliaciones quedan planteadas como trabajo futuro para el Proyecto III.

## Limpieza de las fuentes (detalle)

Desde la raíz del proyecto:

```powershell
uv run python -m no2_madrid.preprocess
```

También se puede ejecutar cada script de `src/no2_madrid/preprocess/` por separado.
Los originales de `data/raw/` se conservan. Los resultados se
guardan por fuente en `data/process/`; la agregación y unión posterior se ejecuta con `build-dataset`. Todos los CSV usan UTF-8, separador `;` y huecos para valores
ausentes. No se imputan datos ni se eliminan picos por ser altos.

| Fuente | Resultado de la limpieza |
| --- | --- |
| NO₂ | CSV anual con `FECHA`, `ANO`, `MES`, `DIA`, `ESTACION`, `NO2` y `VALIDO`. Solo magnitud 8, provincia 28, municipio 79. Una fila por estación y día; se eliminan fechas imposibles como 31 de febrero. Valores negativos, no numéricos o sin validación `V` quedan ausentes, con `VALIDO=0`. Unidad: µg/m³. |
| Meteorología | CSV anual por estación, fecha y magnitud. Conserva `H01`–`H24` y añade `PARAMETRO` y `N_HORAS_VALIDAS`. Las horas sin validación `V` quedan ausentes. Las temperaturas negativas válidas se conservan. |
| Calendario | `calendario_laboral.csv` con `FECHA`, `ANO`, `MES`, `DIA`, `TIPO_DIA`. Elimina `Dia_semana`, `Tipo de Festivo` y `Festividad`. Conserva el calendario completo, incluidas fechas futuras; el día de semana se puede recuperar de `FECHA`. |
| Tráfico | Un `trafico_AAAA_MM.csv.gz` por mes, con intervalos originales y sensores, sin medias. Conserva fecha/hora, año, mes, día, sensor, tipo, intensidad, ocupación, carga, velocidad y número de muestras. Solo registros `error=N`, fecha válida, sensor positivo, tipo URB/C30/M30 y al menos una muestra. M30 se normaliza a C30. Los valores negativos quedan ausentes, y ocupación/carga fuera de 0–100 también. La velocidad urbana queda ausente porque no está disponible. |

Solo se leen los archivos anuales creados por la ingesta de NO₂ y meteorología;
los CSV acumulados descargados manualmente se excluyen para no duplicar datos.
Se eliminan filas exactamente repetidas en NO₂, meteorología y calendario; si
quedan valores contradictorios para la misma clave, el script se detiene.
En tráfico se conservan las filas y su orden tras filtrar: no se supone que dos
horas locales iguales sean duplicados, debido al cambio de hora.

El tráfico se procesa por bloques, con cuatro meses en paralelo, y se comprime
con gzip. Para reducir el uso de memoria se puede ejecutar el script de tráfico
con `--workers 1`. Pandas puede leer el
resultado directamente con `pd.read_csv(ruta, sep=";")`. No se convierten las
intensidades en totales de vehículos: son tasas en vehículos/hora.
`PERIODO_INTEGRACION` es el número de muestras, no una duración en minutos.
Las fechas y horas son las locales del fichero original, sin convertir a UTC.

Cada resultado tiene un `.json` con la firma del original y los recuentos de
limpieza. Tráfico omite los meses ya procesados si el original no ha cambiado.
Para reprocesar un mes:

```powershell
uv run python src/no2_madrid/preprocess/traffic.py --mes 2023_01 --forzar
```

Las series tienen huecos de origen. Se conservan para que la posterior unión
pueda medir la cobertura; la limpieza no fabrica registros mensuales ausentes.
En los originales actuales, el CSV de NO₂ de 2024 termina el 30 de noviembre:
no contiene diciembre. Los datos de 2026 llegan hasta el 31 de octubre.
La agregación diaria y los retrasos disponibles se aplican en dataset.py y features.py.

## Comprobaciones

```powershell
uv run python -m unittest discover -s tests
```

## Documentación de las fuentes

- [NO₂: magnitudes, unidades y formato](https://datos.madrid.es/dataset/201410-0-calidad-aire-diario/resource/201410-63-calidad-aire-diario/download/201410-63-calidad-aire-diario.pdf).
- [Meteorología: magnitudes, unidades y validación](https://datos.madrid.es/dataset/300352-0-meteorologicos-horarios/resource/300352-122-meteorologicos-horarios/download/300352-122-meteorologicos-horarios.pdf).
- [Tráfico: campos, unidades e indicadores de error](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico/resource/208627-81-transporte-ptomedida-historico/download/208627-81-transporte-ptomedida-historico.pdf).

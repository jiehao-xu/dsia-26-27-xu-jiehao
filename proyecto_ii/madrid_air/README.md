# NO₂ Madrid

Proyecto II — Automatización e integración de servicios. El objetivo es predecir
la **concentración media diaria de NO₂ de la red municipal de Madrid**, en µg/m³,
para el siguiente día del histórico disponible.

La referencia municipal es la media aritmética de las mediciones válidas de las
estaciones de calidad del aire. Cada estación pesa igual: no es una media
ponderada por superficie o población ni la concentración de cada barrio.

## Descargar y comprobar desde cero

Los siguientes pasos están pensados para PowerShell en Windows, desde una
carpeta distinta a la del desarrollo. Necesitas Git y Python 3.12, la versión
utilizada para comprobar el proyecto.

### 1. Descargar el repositorio e instalar

Si no tienes uv, instálalo:

```powershell
python -m pip install uv==0.12.9
```

Después clona el repositorio completo y entra en Madrid Air:

```powershell
git clone https://github.com/jiehao-xu/dsia-26-27-xu-jiehao.git dsia-prueba
cd dsia-prueba\proyecto_ii\madrid_air
uv sync --locked --package no2-madrid --group dev
```

El proyecto pertenece al workspace del repositorio y utiliza el `uv.lock` de
su raíz. Conserva la estructura del repositorio completo. GitHub contiene los
cambios que se hayan subido; para probar la última versión deben estar
publicados también los cambios locales recientes.

### 2. Probar el modelo real sin descargar ni entrenar

```powershell
uv run no2-madrid quick-demo
```

Este comando carga el modelo Ridge entrenado con datos reales de Madrid y una
muestra de 32 días incluida en el paquete. No descarga archivos, no reentrena,
no necesita claves y no lee `.env` en su modo `mock` por defecto.
El modelo y la muestra ocupan unos 24 KB en total.

Resultado de referencia: **28,75 µg/m³ para el 1 de noviembre de 2026**, como
media de la red municipal de 24 estaciones. El JSON incluye `scope: "Madrid"`,
`ai_status: "mock"` y `quick_demo.reference_prediction_matches: true`.
Se comprueba que la predicción coincide con la referencia dentro de la tolerancia
numérica. Es una predicción histórica, no una observación ni un pronóstico de hoy.

El resultado se guarda en:

```text
artifacts/quick-demo/reports/runs/prediction_2026-11-01.json
```

Los archivos distribuidos están en `src/no2_madrid/sample/`: modelo joblib,
metadatos, dataset pequeño y manifiesto con firmas SHA-256. La firma del dataset
de entrenamiento completo se conserva separada de la firma de esta muestra.
Las versiones compatibles se instalan con el lockfile del workspace.
La muestra permite probar inferencia, no reentrenar ni reproducir todo el test.

Para ejecutar las pruebas y, opcionalmente, una demostración sintética completa:

```powershell
uv run pytest -q
uv run no2-madrid demo --dir artifacts/prueba
```

En la versión actual deben pasar **25 pruebas**. `demo` genera dos estaciones
sintéticas, construye su media, entrena, evalúa, guarda y carga un modelo nuevo,
y predice con IA `mock`. No lee `.env` ni realiza peticiones a Google. Sus
resultados quedan en `artifacts/prueba/` y no son métricas de datos reales.

### 3. Reproducir la descarga y el entrenamiento completos (opcional)

Esta vía permite reconstruir el dataset y las métricas del proyecto desde sus
fuentes. Los CSV grandes y los artefactos generados en `artifacts/` no se incluyen
en Git; sí se distribuye el modelo pequeño de prueba en `src/no2_madrid/sample/`.

Para ejecutar `run` con el histórico completo, primero debes descargar los datos
y entrenar el modelo en su ubicación por defecto. `quick-demo` utiliza sus
archivos incluidos directamente y no instala el modelo en `artifacts/model.joblib`.
La demostración sintética también mantiene sus resultados separados.

Crea `.env` solo si no existe, para conservar cualquier clave ya configurada:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

Las fuentes municipales no requieren clave. Descarga, limpia, integra y entrena:

```powershell
uv run no2-madrid ingest --source all --start 2023-01-01 --end 2026-10-31
uv run no2-madrid preprocess --workers 1
uv run no2-madrid build-dataset
uv run no2-madrid train --train-end 2024-12-31 --validation-end 2025-12-31
uv run no2-madrid run --ai-mode mock
```

La descarga completa de tráfico ocupa decenas de GB; la descarga, limpieza y
primera agregación pueden tardar. Si ya tienes los CSV limpios, empieza por
`build-dataset`. La limpieza omite meses sin cambios y la agregación utiliza
una caché incremental.

`ingest --source` admite `no2`, `municipal`, `calendar`, `traffic`, `metadata` y
`all`. NO₂ y meteorología se descargan por años y tráfico por meses.
`--refresh` actualiza los ZIP de tráfico. Los catálogos de coordenadas son una
referencia y no se utilizan para filtrar la red por radio.

### 4. Probar Gemini real

Añade tu clave de Google a `.env`, que está excluido de Git:

```dotenv
AI_PROVIDER=google
GOOGLE_API_KEY=tu_clave_de_google
GOOGLE_MODEL=gemini-3.1-flash-lite
```

Para probar Gemini con el modelo y la muestra incluidos, sin descargar ni entrenar:

```powershell
uv run no2-madrid quick-demo --ai-mode real
```

Si has preparado el histórico completo y entrenado su modelo, puedes ejecutar:

```powershell
uv run no2-madrid run --ai-mode real
```

El JSON debe indicar `ai_status: "real"`, `ai_provider: "google"` y un resumen
generado por Gemini. Si indica `ai_status: "fallback"`, la predicción numérica
se ha conservado, pero la petición a Google ha fallado y se ha utilizado una
plantilla. `ai_status: "mock"` identifica una ejecución sin llamada al proveedor.
No publiques la clave ni el archivo `.env`.

## Ejecuciones posteriores y resultados

Una vez preparados los datos y entrenado el modelo:

```powershell
uv run no2-madrid run --ai-mode real
```

`run` actualiza el dataset a partir de los CSV limpios, carga el modelo existente,
predice y solicita el resumen. No descarga ni reentrena. `run --prepare` incluye
la limpieza previa; no programa tareas externas automáticamente.

La salida JSON contiene el ámbito Madrid, el valor de NO₂ en µg/m³, la definición
del objetivo, la red de estaciones, la cobertura del NO₂ de referencia, las
fechas límite de información, el modelo, el error histórico y el resumen.
El resultado se guarda en `reports/runs/prediction_AAAA-MM-DD.json`; las métricas
en `reports/metrics.json` y el informe legible en `reports/evaluation.md`.

La fecha automática es el siguiente día del histórico de NO₂ disponible, no
necesariamente mañana. En la evaluación documentada, el histórico termina el
31 de octubre de 2026 y se predice el 1 de noviembre de 2026. Una nueva descarga
puede contener datos actualizados y cambiar las fechas y los resultados.

Opciones globales, antes del subcomando:

```powershell
uv run no2-madrid --data-dir data --output-dir . build-dataset
```

Como alternativa sin uv, instala `requirements.txt` con pip y ejecuta
`python -m pip install --no-deps -e .` desde esta carpeta. Los subcomandos pueden
invocarse mediante `python -m no2_madrid` en lugar de `no2-madrid`.

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

### Licencias de NO₂ y tráfico histórico

Los datos de [NO₂ diario](https://datos.madrid.es/dataset/201410-0-calidad-aire-diario)
y [tráfico histórico](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico)
proceden del Ayuntamiento de Madrid y sus fichas oficiales indican la licencia
[Creative Commons Atribución 4.0 Internacional (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/deed.es).

En este proyecto se han limpiado, filtrado y agregado para construir el dataset
de predicción. Se reconoce al Ayuntamiento de Madrid como fuente, se enlazan
los conjuntos originales y la licencia, y se indican estas transformaciones.
El proyecto no implica respaldo ni aprobación del Ayuntamiento de Madrid.

Estas condiciones corresponden a los datos y no establecen la licencia del
código desarrollado en el repositorio.

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

Se comparan persistencia, Ridge con NO₂/calendario y dos parejas de modelos: Ridge y HistGradientBoostingRegressor, cada uno con meteorología y calendario, con y sin variables de tráfico. Los modelos incluyen
imputación por mediana, indicadores de ausencia y escalado en una Pipeline
sklearn. Se selecciona por MAE de validación y después se ajusta el ganador con
entrenamiento y validación; test no se utiliza para ajustar ni seleccionar el modelo. La persistencia también
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

Última evaluación municipal del 22 de noviembre de 2026: red de 24 estaciones, 1.368 objetivos diarios válidos y tráfico procesado hasta octubre de 2026. Modelo elegido por validación: ridge_no_traffic (NO₂ histórico, calendario y meteorología). MAE de test: 5,054 µg/m³; RMSE: 6,671 µg/m³, sobre 304 días. La inferencia del modelo actualizado se comprobó en mock; la predicción histórica para el 1/11/2026 es 28,75 µg/m³.
Las cifras del modelo anterior de una sola estación no son las métricas de
Madrid. Su evidencia se conserva etiquetada en `reports/archive/station_4/`.
El tráfico procesado cubre los 46 meses de enero de 2023 a octubre de 2026. Se completaron noviembre y diciembre de 2025 y enero a octubre de 2026, y se repite la evaluación con esas entradas disponibles. La cobertura efectiva por partición se registra en el informe de aportación del tráfico.


### Evaluación específica del tráfico

La comparación mantiene las mismas fechas, objetivos, algoritmo y parámetros,
y cambia únicamente la inclusión de variables de tráfico. Se comparan Ridge
sin tráfico frente a Ridge completo y el mismo par para el modelo de árboles,
conservando NO₂ histórico, calendario y meteorología en ambas versiones.

Los modelos se eligen por MAE de validación. Después se ajustan con entrenamiento
y validación y se reportan MAE, RMSE, mejora absoluta y porcentual y error mensual
en las mismas fechas de 2026. Una mejora positiva indica menor error con tráfico;
una negativa indica empeoramiento. También se publica la proporción de días
con intensidad de tráfico disponible para cada partición.

Los resultados están en `reports/traffic_evaluation.md` y
`reports/traffic_evaluation.json`, además del informe general. El JSON incluye
las fechas exactas y su firma para comprobar que la comparación usa los mismos días.
El test de 2026 ya se había consultado anteriormente: esta comparación es
exploratoria, no una evaluación externa nueva ni una demostración causal.
La inclusión de tráfico no garantiza que mejore el modelo.

#### Resultado con tráfico completo

La intensidad de tráfico está disponible en los 304 días del test (100 %),
así como en todos los días evaluados de entrenamiento y validación.

| Modelo | MAE sin tráfico | MAE con tráfico |
|---|---|---|
| Ridge | 5,054 | 5,072 |
| Árboles | 5,500 | 5,484 |

Valores en µg/m³. En esta comparación, el tráfico empeora ligeramente Ridge y
mejora ligeramente el modelo de árboles, que sigue teniendo más error que
Ridge. El modelo seleccionado por validación utiliza NO₂, calendario y
meteorología, sin tráfico. Estas diferencias pequeñas no demuestran por sí
solas una mejora generalizable; las métricas y el desglose mensual quedan
publicados para revisar el resultado.

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

Datos voluminosos, artefactos generados en `artifacts/` y ejecuciones quedan fuera de Git; se
entregan instrucciones para reentrenar y dependencias bloqueadas en el `uv.lock` de la raíz del repositorio, compartido por el workspace.
Solo cargar artefactos joblib propios y fiables. Los modelos anteriores de una
estación son incompatibles con el nuevo contrato municipal y no se reutilizan.

La excepción es el paquete pequeño de prueba `src/no2_madrid/sample/`, que incluye el modelo entrenado y datos reales agregados para ejecutar `quick-demo` desde una descarga limpia.

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

Puedes consultar las ejecuciones y los resultados de las pruebas en [GitHub Actions del repositorio](https://github.com/jiehao-xu/dsia-26-27-xu-jiehao/actions).

Las pruebas cubren limpieza, media municipal, cobertura mínima, agregación
entre estaciones, tráfico independiente del tamaño de bloque, retardos y
ausencia de información futura, persistencia/carga/inferencia del modelo,
cliente Google simulado y alternativa ante errores. También se prueba la inferencia real con la muestra distribuida desde una carpeta vacía, sin descargar ni entrenar, y la detección de archivos de muestra modificados. La integración utiliza
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

.
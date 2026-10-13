# Proyecto I

[![CI Proyecto I](https://github.com/jiehao-xu/dsia-26-27-xu-jiehao/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jiehao-xu/dsia-26-27-xu-jiehao/actions/workflows/ci.yml)

Proyecto I forma parte del repositorio `jiehao-xu/dsia-26-27-xu-jiehao`, dentro de la carpeta `proyecto_i`. Mantiene su propio `.gitignore` y la configuración de sus pasos de CI en `.github/actions/ci/action.yml`. El proyecto contiene dos aplicaciones: `ventas_app`, para validar y procesar ventas, e `internet_app`, para analizar las variables educativas de la EPA. Ambas separan lectura y escritura, validación, métricas y ejecución por terminal, y cuentan con pruebas de `pytest`.

Ejecuta los comandos de este README en **Bash desde la carpeta `proyecto_i`**. Las aplicaciones aceptan rutas absolutas o relativas a esa carpeta.

## Estructura

```text
proyecto_i/                         # Carpeta del proyecto en el repositorio
├── .github/actions/ci/action.yml
├── .gitignore
├── ventas_app/
│   ├── cli.py
│   ├── loader.py
│   ├── validator.py
│   ├── metrics.py
│   ├── datos.py
│   └── errors.py
├── internet_app/
│   ├── cli.py
│   ├── loader.py
│   ├── contracts.py
│   ├── validator.py
│   ├── metrics.py
│   └── errors.py
├── tests/
│   ├── ventas/
│   └── internet/
├── data/
├── pyproject.toml
├── uv.lock
├── requirements.txt
└── README.md
```

| Módulo | Responsabilidad |
| --- | --- |
| `loader.py` | Leer archivos y guardar los resultados. |
| `contracts.py` | Definir el contrato Pydantic de las variables EPA utilizadas. |
| `validator.py` | Comprobar la estructura y las reglas de los datos. En EPA también permite renombrar columnas. |
| `metrics.py` | Calcular importes, totales o indicadores educativos. |
| `cli.py` | Leer argumentos y coordinar la ejecución de las etapas. |
| `errors.py` | Definir `DataLoadError`, `DataSaveError` y `ValidationError` de cada aplicación. |

## Instalar dependencias

El proyecto requiere Python 3.12 o superior. La CI utiliza Python 3.12.

Con `uv` instalado:

```bash
uv sync --group dev
```

Este comando crea `.venv` e instala las dependencias del proyecto y de desarrollo, incluidas `pytest` y `pytest-cov`. `uv.lock` registra la resolución de dependencias.

Para ejecutar `pytest` directamente, activa el entorno en Git Bash (Windows):

```bash
source .venv/Scripts/activate
```

En Linux o macOS:

```bash
source .venv/bin/activate
```

Como alternativa, en un entorno Python 3.12 activado, puedes instalar las versiones fijadas para CI:

```bash
pip install -r requirements.txt
```

`requirements.txt` incluye `pandas`, `pydantic`, `pytest` y `pytest-cov` y se utiliza en GitHub Actions.

## Parte A: ventas

### Entrada y validación

El archivo de entrada es `data/ventas.csv`, con las columnas obligatorias:

```text
fecha,region,producto,unidades,precio_unitario,cliente_id
```

`SalesValidator` comprueba que estén presentes; admite columnas adicionales. Las fechas se convierten con el formato `%Y-%m-%d`: una fecha inválida detiene la ejecución. Las unidades y los precios se convierten a valores numéricos; las filas con valores ausentes, no numéricos, cero o negativos quedan en el DataFrame de errores.

`validar_ventas()` devuelve `(validos, errores)` sin modificar el DataFrame original y añade `importe = unidades × precio_unitario` a las filas válidas. La CLI guarda las ventas válidas; actualmente no exporta el DataFrame de errores.

### Métricas y salida

La CLI elimina `cliente_id` y añade a cada venta:

| Columna | Contenido |
| --- | --- |
| `importe` | Importe de esa venta. |
| `total_by_region` | Suma de los importes válidos de su región. |
| `total_by_month` | Suma de los importes válidos de su año y mes. |
| `total_by_product` | Suma de los importes válidos de su producto. |

Las métricas utilizan `transform("sum")` para conservar una fila por venta. Los totales se repiten entre filas del mismo grupo; no se deben sumar esas columnas para obtener el total general.

`datos.py` también define `SalesRecord`, una dataclass inmutable con la propiedad `amount`. El flujo actual de la CLI trabaja con DataFrames.

### Ejecución

```bash
uv run python -m ventas_app.cli --input data/ventas.csv --output data/ventas_validas.csv
```

El guardado comprueba que exista la carpeta de destino y permite crear un archivo nuevo. Si ya existe, lo sobrescribe. El CSV se guarda sin el índice de pandas.

## Parte B: análisis educativo de la EPA

### Datos utilizados

- `data/EPA_2026T2.tab`: microdatos separados por tabulaciones.
- `data/dr_EPA_2026.json`: diseño de variables, descripciones y tablas de códigos.
- `data/dr_EPA_2026.xlsx`: documentación adicional; la aplicación utiliza el JSON.

El objetivo a largo plazo es trabajar en la predicción del abandono educativo. La implementación actual prepara y calcula indicadores descriptivos; todavía no entrena un modelo predictivo.

### Lectura de archivos

`internet_app.loader.load()` selecciona la lectura según la extensión:

| Extensión | Resultado |
| --- | --- |
| `.csv` | DataFrame con valores leídos como texto. |
| `.tab` | DataFrame leído con `sep="\t"` y valores como texto. |
| `.json` | Diccionario de Python. |

Leer los códigos como texto conserva ceros iniciales como `"01"`. La función rechaza archivos inexistentes y extensiones no admitidas. También rechaza JSON mal formado o cuyo contenido no sea un objeto.

### Contrato Pydantic

`contracts.py` define `EPARecord(BaseModel)`. El contrato conserva los nombres originales del archivo de entrada, sin alias ni renombrado en esta etapa:

| Columna | Significado |
| --- | --- |
| `CCAA` | Comunidad autónoma. |
| `SEXO1` | Sexo: `1` hombre, `6` mujer. |
| `NIVEL` | Tipo de registro: `1` persona de 16 o más años, `2` menor de 16. |
| `EDAD1` | Grupo de edad; no es una edad exacta. |
| `NFORMA` | Máximo nivel educativo alcanzado. |
| `CURSR` | Formación reglada en las últimas cuatro semanas. |
| `CURSNR` | Formación no reglada en las últimas cuatro semanas. |
| `FACTOREL` | Factor de elevación para estimar la población. |

El modelo utiliza `Literal` para los códigos y `Field` para descripciones y restricciones. Los comentarios del contrato explican el significado de cada código. `FACTOREL` debe ser numérico, finito y mayor que cero. Los campos educativos admiten valores nulos para menores, pero son obligatorios en adultos. También se comprueba la coherencia entre `NIVEL` y `EDAD1`.

`crear_contrato()` completa la información con las descripciones y etiquetas del JSON. `model_dump()` conserva los nombres originales y `model_json_schema()` publica el esquema de tipos, descripciones y valores permitidos.

### Validación y preprocesado

`EPAValidator` ofrece estos métodos:

| Método | Comportamiento |
| --- | --- |
| `validar_columnas()` | Exige las ocho columnas del contrato, rechaza duplicadas y permite columnas adicionales. |
| `validar_valores()` | Aplica Pydantic a cada fila y comprueba los códigos con el JSON. Informa del índice de la fila cuando falla. |
| `normalizar_columnas()` | Devuelve una copia con nombres descriptivos y rechaza colisiones de nombres. |

El renombrado es una operación posterior y explícita, separada del contrato:

```python
validador = EPAValidator(diccionario)
validador.validar_valores(frame)
datos = validador.normalizar_columnas(frame)
```

Por ejemplo, `CCAA` pasa a `comunidad_autonoma` y `EDAD1` a `grupo_edad`. La CLI y las métricas actuales conservan los nombres originales. `preparar_datos()` valida, elimina espacios de los códigos y convierte `FACTOREL` a número sin modificar la entrada. Si hay un error de validación, la ejecución se detiene antes de guardar.

### Métricas educativas

`preparar_indicador()` selecciona personas con `NIVEL == "1"` y `EDAD1 == "20"`, es decir, de **20–24 años**, y añade las etiquetas individuales:

- `baja_formacion`: nivel educativo `AN`, `P1`, `P2` o `S1`.
- `participa_formacion`: `CURSR` o `CURSNR` igual a `1` o `2`; las vacaciones cuentan como participación.
- `baja_formacion_sin_estudios`: bajo nivel educativo y ausencia de formación reciente.

| Función | Resultado |
| --- | --- |
| `poblacion_estimada()` | Suma de `FACTOREL` de las personas seleccionadas. |
| `poblacion_indicador()` | Suma de factores de quienes cumplen el indicador. |
| `tasa_ponderada()` | Porcentaje ponderado con baja formación y sin estudios recientes. |
| `tasa_baja_formacion()` | Porcentaje ponderado con bajo nivel educativo, estudien actualmente o no. |
| `tasa_participacion_formacion()` | Porcentaje ponderado que participa en formación. |

Las tasas se calculan como `100 × suma de factores de quienes cumplen / suma total de factores`. La población se expresa en personas, no en miles. Sin personas analizables, las sumas devuelven cero y las tasas `None`.

Este indicador no reproduce la tasa oficial de abandono de **18–24 años**, porque `EDAD1` agrupa 16–19 y no permite aislar los 18 y 19 años. La [definición oficial del INE](https://ine.es/jaxiT3/Tabla.htm?L=0&t=69788) utiliza ese intervalo de 18–24 años.

### Ejecución y salida

```bash
uv run python -m internet_app.cli --input data/EPA_2026T2.tab --output data/resumen_educativo.csv
```

`--input` y `--output` son obligatorios. `--dictionary` permite cambiar el diccionario predeterminado, `data/dr_EPA_2026.json`.

La salida es un CSV de **una fila con el resumen global**: `grupo_edad`, `registros`, `poblacion_estimada`, `poblacion_indicador`, `tasa_indicador_20_24`, `tasa_baja_formacion_20_24` y `tasa_formacion_20_24`. Sin personas de 20–24 años se guarda una fila con población cero y tasas vacías. La carpeta de destino debe existir; un archivo existente se sobrescribe.

En la comprobación del fichero real se validaron 114.021 registros y se seleccionaron 5.652 personas de 20–24 años. El indicador ponderado obtenido fue del 15,24 % para ese grupo.

## Tests y cobertura

Cada aplicación tiene su propio `conftest.py` con fixtures compartidas. Las pruebas utilizan datos pequeños y resultados conocidos. `tmp_path` proporciona archivos temporales y evita modificar los archivos reales de entrada.

| Fichero de tests | Qué comprueba |
| --- | --- |
| `test_loader.py` | Lectura, conservación de códigos y errores de archivos o guardado. |
| `test_contracts.py` (EPA) | Tipos, códigos, factores, coherencia de edad, campos educativos y metadatos Pydantic. |
| `test_validator.py` | Columnas obligatorias y casos de validación; en EPA, normalización de columnas. |
| `test_metrics.py` | Resultados conocidos, ponderación, datos vacíos y conservación de la entrada. |
| `test_cli.py` | Ejecución del flujo, resultados guardados, argumentos y errores. |
| `test_datos.py` (ventas) | Cálculo de `amount` e inmutabilidad de `SalesRecord`. |

La prueba de EPA que ejecuta el módulo desde otro proceso tiene el marcador `integration`, registrado en `pyproject.toml`. `--import-mode=importlib` permite que ambas carpetas tengan archivos de tests con los mismos nombres.

Todos los tests, con salida compacta:

```bash
pytest -q
```

Tests que no tienen el marcador `integration`:

```bash
pytest -q -m "not integration"
```

Cobertura conjunta de ambos paquetes, mostrando las líneas sin cubrir y exigiendo un mínimo del 60 %:

```bash
pytest --cov=ventas_app --cov=internet_app --cov-report=term-missing --cov-fail-under=60
```

El umbral se aplica a la cobertura conjunta, no por separado a cada paquete. La cobertura mide qué código se ejecuta durante las pruebas; no garantiza por sí sola que se comprueben todos los comportamientos.

## Integración continua (CI)

El workflow de entrada está en `.github/workflows/ci.yml`, en la raíz del repositorio padre para que GitHub Actions lo detecte. Tras el checkout llama a la acción local `proyecto_i/.github/actions/ci/action.yml`, que contiene los pasos de Python, instalación y tests. Se ejecuta con `push` a `main`, con `pull_request` y, una vez publicado, permite ejecución manual mediante `workflow_dispatch`.

Los pasos son:

1. Checkout del repositorio.
2. Configuración de Python 3.12.
3. Instalación con `pip install -r requirements.txt`.
4. Ejecución de todos los tests, incluidos los de integración, con cobertura de `ventas_app` e `internet_app` y `--cov-fail-under=60`.

Los comandos de instalación y tests se ejecutan desde `proyecto_i`. La caché de dependencias utiliza `proyecto_i/requirements.txt`. Las versiones principales están fijadas en `requirements.txt`. Los entornos virtuales, cachés de pytest e informes de cobertura se excluyen mediante `.gitignore`.


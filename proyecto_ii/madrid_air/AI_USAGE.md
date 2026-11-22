# Uso de inteligencia artificial durante el desarrollo

## Asistencia durante el desarrollo

He usado Codex de OpenAI durante el desarrollo para resolver dudas, revisar
errores y ayudarme a escribir y corregir código, pruebas y documentación.
También le he pedido revisar el enunciado conmigo para comprobar qué faltaba
y hacer que el proyecto fuera más fácil de entender.

En concreto, he pedido ayuda para:

- Ordenar los módulos y explicar mejor qué parte descarga los datos, cuál los
  limpia y cuál entrena el modelo.
- Entender los errores que me han aparecido al ejecutar el programa: el modelo
  que todavía no estaba entrenado, el aviso del entorno virtual y el problema
  con el certificado del servidor de datos. También pedí mensajes más claros
  para saber qué hacer en cada caso.
- Revisar las fechas, los datos que faltan y la actualización de los CSV, para
  evitar duplicados y no perder el archivo anterior si falla la escritura.
- Mejorar las explicaciones de los resultados. Al principio eran demasiado
  simples, así que pedí usar Gemini de verdad, explicar todas las filas y añadir
  datos de contexto para que el texto no se limitara a repetir la predicción.
- Añadir pruebas del funcionamiento y de los posibles errores, simulando las
  respuestas de los servicios para no necesitar conexión ni claves en los tests.
- Simplificar los archivos y corregir la documentación para reflejar el flujo
  actual y sus limitaciones.

He incorporado estas mejoras y he ido revisando los resultados al ejecutar el
programa. La ayuda ha incluido generar código, tests y documentación, además
de corregirlos; no se ha limitado a cambiar la redacción.

## IA integrada y verificacion real

- Proveedor: Google Gemini API; SDK google-genai.
- Tarea: generar un resumen en espanol de la prediccion numerica de sklearn.
- Modelo verificado: gemini-3.1-flash-lite.
- Prueba real del 22 de noviembre de 2026: respuesta HTTP 200 y ai_status=real, sin recurrir a la plantilla.
- Resultado guardado en reports/runs/prediction_2026-11-01.json.
- Las pruebas y CI usan mock; la clave permanece en la configuracion local y no se incluye en la documentacion.

## Corrección del ámbito de predicción

El objetivo vigente es la media diaria de las estaciones válidas de la red
municipal de Madrid, con al menos un 75 % de cobertura. Se retiró la selección
de una sola estación y el filtro de tráfico a 500 metros. El modelo se vuelve
a entrenar con este objetivo; las métricas de la estación 4 quedan archivadas
y no se atribuyen al conjunto de Madrid. Gemini recibe explícitamente el ámbito
Madrid y el número de estaciones de la red.


Verificación del objetivo municipal: el 22 de noviembre de 2026 se reentrenó con la media de la red de 24 estaciones y se ejecutó Gemini real (HTTP 200, ai_status=real). La salida actual declara scope=Madrid; la evidencia de la estación 4 queda archivada y separada.

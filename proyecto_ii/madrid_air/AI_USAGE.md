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
programa. .


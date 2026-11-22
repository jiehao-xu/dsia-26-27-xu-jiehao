# Muestra real para prueba rápida

Este directorio se distribuye en Git y con el paquete Python. Contiene el modelo
sklearn entrenado con datos reales de Madrid y 32 días del dataset diario
agregado para reconstruir sus entradas. No contiene claves ni archivos brutos.

Ejecutar: `uv run no2-madrid quick-demo`. No descarga ni reentrena y utiliza
IA `mock` por defecto. `--ai-mode real` permite utilizar Gemini con la clave local.

La predicción y su tolerancia se comprueban contra manifest.json. Los hashes
permiten detectar copias alteradas. El modelo joblib procede de este proyecto;
no debe sustituirse por artefactos de origen desconocido.

`model.json` registra la red, variables, periodo de entrenamiento y versiones.
Su firma del dataset de entrenamiento corresponde al histórico completo;
`daily.json` registra por separado la firma de esta muestra de inferencia.
La muestra no permite reentrenar ni reproducir las métricas de todo el test.

Datos: Ayuntamiento de Madrid, portal Datos Abiertos. Se han limpiado, filtrado
y agregado. Licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es).
Fuentes: [NO₂](https://datos.madrid.es/dataset/201410-0-calidad-aire-diario),
[meteorología](https://datos.madrid.es/dataset/300352-0-meteorologicos-horarios),
[tráfico](https://datos.madrid.es/dataset/208627-0-transporte-ptomedida-historico) y
[calendario](https://datos.madrid.es/dataset/300082-0-calendario_laboral).
El Ayuntamiento no respalda las predicciones del proyecto.

Los archivos de texto de esta muestra usan saltos de l?nea LF, fijados mediante
.gitattributes. Sus firmas se calculan sobre esos bytes; el modelo joblib se
trata como binario. Se conserva la validaci?n de integridad antes de cargarlo.

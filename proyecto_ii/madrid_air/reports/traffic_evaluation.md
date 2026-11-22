
## Aportación del tráfico

Cada pareja mantiene el algoritmo, los parámetros, el resto de variables y las fechas de evaluación.
Mejora positiva significa menor error al añadir tráfico; negativa significa empeoramiento.

| Modelo | Partición | Sin tráfico MAE | Con tráfico MAE | Mejora MAE |
|---|---|---|---|---|
| ridge | validation | 5.735 | 5.797 | -0.062 |
| ridge | test | 5.054 | 5.072 | -0.017 |
| hist | validation | 6.743 | 6.582 | 0.161 |
| hist | test | 5.500 | 5.484 | 0.016 |

### Cobertura de las entradas de tráfico

| Partición | Días evaluados | Días con intensidad disponible | Cobertura |
|---|---|---|---|
| train | 699 | 699 | 100.0% |
| validation | 362 | 362 | 100.0% |
| test | 304 | 304 | 100.0% |

Comparación exploratoria: 2026 ya se había consultado; no es una evaluación externa nueva ni prueba causal.

La selección del modelo usa validación. Esta comparación mide utilidad predictiva, no causalidad.
Los datos usados son históricos con retrasos supuestos de disponibilidad.
Desglose mensual, RMSE y fechas exactas: traffic_evaluation.json.

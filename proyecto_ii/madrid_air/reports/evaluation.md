# Evaluación NO₂ — Madrid

Modelo seleccionado en validación: **ridge_no_traffic**.

Objetivo: media de la red municipal de Madrid (24 estaciones).

Predicciones históricas secuenciales; no equivalen a un servicio operativo.

| Partición | Inicio | Fin | Días |
|---|---|---|---|
| train | 2023-01-02 | 2024-11-30 | 699 |
| validation | 2025-01-02 | 2025-12-31 | 362 |
| test | 2026-01-01 | 2026-10-31 | 304 |

| Validación | MAE | RMSE |
|---|---|---|
| persistence | 6.751 | 8.970 |
| ridge_basic | 5.735 | 7.548 |
| ridge_no_traffic | 5.735 | 7.521 |
| ridge_full | 5.797 | 7.574 |
| hist_no_traffic | 6.743 | 8.843 |
| hist_full | 6.582 | 8.766 |

| Test fuera del ajuste | MAE | RMSE |
|---|---|---|
| selected | 5.054 | 6.671 |
| persistence | 5.568 | 7.623 |

Métricas en µg/m³; el MAE no es un intervalo de confianza.

Desglose mensual y concentraciones altas: `metrics.json`.

![Evaluación](figures/evaluation.png)


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

# Evaluación NO₂ — Madrid

Modelo seleccionado en validación: **ridge_basic**.

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
| ridge_full | 5.843 | 7.628 |
| hist_full | 6.504 | 8.621 |

| Test reservado | MAE | RMSE |
|---|---|---|
| selected | 5.160 | 6.830 |
| persistence | 5.568 | 7.623 |

Métricas en µg/m³; el MAE no es un intervalo de confianza.

Desglose mensual y concentraciones altas: `metrics.json`.

![Evaluación](figures/evaluation.png)

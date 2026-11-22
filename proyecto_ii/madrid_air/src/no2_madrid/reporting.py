"""Informe exportable de evaluación temporal."""


def training_report(folder, report, evaluation):
    import os
    os.environ.setdefault("MPLCONFIGDIR", str((folder / ".matplotlib").resolve()))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = folder / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    evaluation[["observed", "predicted"]].plot(ax=axes[0], linewidth=.8)
    axes[0].set_ylabel("NO₂ (µg/m³)")
    (evaluation.predicted - evaluation.observed).plot.hist(ax=axes[1], bins=30)
    axes[1].set_xlabel("Predicción − observado (µg/m³)")
    fig.tight_layout()
    fig.savefig(figures / "evaluation.png", dpi=160)
    plt.close(fig)
    lines = ["# Evaluación NO₂ — Madrid", "", f"Modelo seleccionado en validación: **{report['selected']}**.",
             "", f"Objetivo: media de la red municipal de Madrid ({report['n_stations']} estaciones).",
             "", "Predicciones históricas secuenciales; no equivalen a un servicio operativo.", "",
             "| Partición | Inicio | Fin | Días |", "|---|---|---|---|"]
    for name, part in report["partitions"].items():
        lines.append(f"| {name} | {part['start']} | {part['end']} | {part['n']} |")
    lines += ["", "| Validación | MAE | RMSE |", "|---|---|---|"]
    for name, m in report["validation"].items():
        lines.append(f"| {name} | {m['mae']:.3f} | {m['rmse']:.3f} |")
    lines += ["", "| Test fuera del ajuste | MAE | RMSE |", "|---|---|---|"]
    for name in ("selected", "persistence"):
        m = report["test"][name]
        lines.append(f"| {name} | {m['mae']:.3f} | {m['rmse']:.3f} |")
    lines += ["", "Métricas en µg/m³; el MAE no es un intervalo de confianza.", "",
              "Desglose mensual y concentraciones altas: `metrics.json`.", "", "![Evaluación](figures/evaluation.png)", ""]
    lines += traffic_report_lines(report["traffic_evaluation"])
    (folder / "traffic_evaluation.md").write_text("\n".join(traffic_report_lines(report["traffic_evaluation"])), encoding="utf-8")
    (folder / "evaluation.md").write_text("\n".join(lines), encoding="utf-8")


def traffic_report_lines(report):
    lines = ["", "## Aportación del tráfico", "",
             "Cada pareja mantiene el algoritmo, los parámetros, el resto de variables y las fechas de evaluación.",
             "Mejora positiva significa menor error al añadir tráfico; negativa significa empeoramiento.", "",
             "| Modelo | Partición | Sin tráfico MAE | Con tráfico MAE | Mejora MAE |", "|---|---|---|---|---|"]
    for family, pair in report["pairs"].items():
        for split in ("validation", "test"):
            m = pair[split]
            lines.append(f"| {family} | {split} | {m['without_traffic']['mae']:.3f} | {m['with_traffic']['mae']:.3f} | {m['mae_improvement']:.3f} |")
    lines += ["", "### Cobertura de las entradas de tráfico", "",
              "| Partición | Días evaluados | Días con intensidad disponible | Cobertura |", "|---|---|---|---|"]
    for split, coverage in report["coverage"].items():
        lines.append(f"| {split} | {coverage['days']} | {coverage['days_with_traffic']} | {coverage['fraction_days_with_traffic']:.1%} |")
    lines += ["", report["interpretation"] + ".", "",
              "La selección del modelo usa validación. Esta comparación mide utilidad predictiva, no causalidad.",
              "Los datos usados son históricos con retrasos supuestos de disponibilidad.",
              "Desglose mensual, RMSE y fechas exactas: traffic_evaluation.json.", ""]
    return lines

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
    lines += ["", "| Test reservado | MAE | RMSE |", "|---|---|---|"]
    for name in ("selected", "persistence"):
        m = report["test"][name]
        lines.append(f"| {name} | {m['mae']:.3f} | {m['rmse']:.3f} |")
    lines += ["", "Métricas en µg/m³; el MAE no es un intervalo de confianza.", "",
              "Desglose mensual y concentraciones altas: `metrics.json`.", "", "![Evaluación](figures/evaluation.png)", ""]
    (folder / "evaluation.md").write_text("\n".join(lines), encoding="utf-8")

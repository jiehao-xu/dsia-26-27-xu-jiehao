import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error


def evaluate(y_true, prediction, baseline):
    """Compara el bosque y la persistencia con los valores reales de NO2.

    MAE es el error absoluto medio; RMSE penaliza más los errores grandes.
    Ambos se expresan en las mismas unidades que el NO2: microgramos/m³.
    """
    return {"mae": float(mean_absolute_error(y_true, prediction)),
            "rmse": float(np.sqrt(mean_squared_error(y_true, prediction))),
            "baseline_mae": float(mean_absolute_error(y_true, baseline)),
            "baseline_rmse": float(np.sqrt(mean_squared_error(y_true, baseline)))}

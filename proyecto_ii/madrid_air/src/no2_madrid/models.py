"""Referencia persistente con contrato de regresor sklearn."""
import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.utils.validation import check_array, check_is_fitted


class PersistenceRegressor(RegressorMixin, BaseEstimator):
    def fit(self, X, y=None):
        array = check_array(X)
        if array.shape[1] != 1:
            raise ValueError("La persistencia necesita una sola variable.")
        self.n_features_in_ = array.shape[1]
        return self

    def predict(self, X):
        check_is_fitted(self)
        array = check_array(X)
        if array.shape[1] != self.n_features_in_:
            raise ValueError("Número de variables incompatible.")
        return np.asarray(array[:, 0])

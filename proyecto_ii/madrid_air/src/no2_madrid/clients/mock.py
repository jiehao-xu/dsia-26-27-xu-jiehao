from no2_madrid.clients.base import PredictionContext


class MockClient:
    def explain(self, context: PredictionContext) -> str:
        return (f"Estimación de NO₂ para {context.scope} el {context.date} (media de la red de {context.network_stations} estaciones): "
                f"{context.no2:.2f} µg/m³. Hay {context.missing_features} entradas ausentes. "
                f"El MAE histórico de test es {context.test_mae:.2f} µg/m³ y no representa "
                "un intervalo de confianza. Resumen por plantilla; no es una medición ni una recomendación sanitaria.")

import pandas as pd


class SalesValidator:
    
    def validar_ventas(self, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Reglas mínimas:
            unidades numérica y > 0
            precio_unitario numérico y > 0
            columnas derivadas: importe = unidades * precio_unitario solo en válidos
        Devuelve (validos, errores)
        """
        work = frame.copy()
        work["unidades"] = pd.to_numeric(work["unidades"], errors="coerce")
        work["precio_unitario"] = pd.to_numeric(work["precio_unitario"], errors="coerce")

        ok = (
            work["unidades"].notna()
            & (work["unidades"] > 0)
            & work["precio_unitario"].notna()
            & (work["precio_unitario"] > 0)
        )

        validos = work.loc[ok].copy()
        errores = work.loc[~ok].copy()
        validos["importe"] = validos["unidades"] * validos["precio_unitario"]
        return validos, errores

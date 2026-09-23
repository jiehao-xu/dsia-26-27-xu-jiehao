
from dataclasses import dataclass    
from datos import SalesRecord
import pandas as pd

class SalesMetrics:
    def total_by_region(self, records: pd.DataFrame) -> dict[str, float]:
        return (
            records.groupby("region")["importe"]
            .sum()
            .sort_values(ascending=False)
            .to_dict()
        )



import numpy as np

from app.models.schemas import MetricSnapshot
from app.services.ingestion import DatasetBundle


class KPIAnalyzer:
    def build_metric_snapshots(self, dataset: DatasetBundle) -> list[MetricSnapshot]:
        snapshots: list[MetricSnapshot] = []

        for metric in dataset.metric_columns:
            series = dataset.frame[metric].dropna().astype(float)
            if series.empty:
                continue

            latest_value = float(series.iloc[-1])
            previous_value = float(series.iloc[-2]) if len(series) > 1 else None
            absolute_change = (
                latest_value - previous_value if previous_value is not None else None
            )
            percent_change = (
                (absolute_change / previous_value)
                if previous_value not in (None, 0)
                else None
            )

            snapshots.append(
                MetricSnapshot(
                    metric=metric,
                    latest_value=latest_value,
                    previous_value=previous_value,
                    absolute_change=absolute_change,
                    percent_change=percent_change,
                    mean_value=float(series.mean()),
                    min_value=float(series.min()),
                    max_value=float(series.max()),
                    trend_direction=self._infer_trend_direction(series.to_numpy()),
                )
            )

        return snapshots

    def _infer_trend_direction(self, values: np.ndarray) -> str:
        if len(values) < 2:
            return "flat"

        x_axis = np.arange(len(values))
        slope = float(np.polyfit(x_axis, values, 1)[0])
        average = float(np.mean(values)) or 1.0
        relative_slope = slope / average

        if relative_slope > 0.01:
            return "up"
        if relative_slope < -0.01:
            return "down"
        return "flat"

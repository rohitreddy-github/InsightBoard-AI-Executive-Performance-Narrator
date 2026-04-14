import math

from app.models.schemas import AnomalyInsight, MetricSnapshot
from app.services.ingestion import DatasetBundle


class AnomalyDetector:
    def __init__(self, zscore_threshold: float, change_threshold: float) -> None:
        self.zscore_threshold = zscore_threshold
        self.change_threshold = change_threshold

    def detect(self, dataset: DatasetBundle, snapshots: list[MetricSnapshot]) -> list[AnomalyInsight]:
        snapshot_map = {snapshot.metric: snapshot for snapshot in snapshots}
        anomalies: list[AnomalyInsight] = []

        for metric in dataset.metric_columns:
            series = dataset.frame[metric].dropna().astype(float)
            if len(series) < 2:
                continue

            snapshot = snapshot_map.get(metric)
            if snapshot is None:
                continue

            mean = float(series.mean())
            std = float(series.std(ddof=0))
            latest = float(series.iloc[-1])
            zscore = 0.0 if math.isclose(std, 0.0) else (latest - mean) / std

            if abs(zscore) >= self.zscore_threshold:
                anomalies.append(
                    AnomalyInsight(
                        metric=metric,
                        severity=self._severity_from_zscore(abs(zscore)),
                        latest_value=latest,
                        baseline_value=mean,
                        reason=(
                            f"Latest value deviates from the historical mean by "
                            f"{zscore:.2f} standard deviations."
                        ),
                    )
                )
                continue

            change = snapshot.percent_change
            if change is not None and abs(change) >= self.change_threshold:
                anomalies.append(
                    AnomalyInsight(
                        metric=metric,
                        severity="medium" if abs(change) >= (self.change_threshold * 1.5) else "low",
                        latest_value=latest,
                        baseline_value=float(series.iloc[-2]),
                        reason=(
                            f"Month-over-month change reached {change * 100:.1f}%, exceeding "
                            "the configured alert threshold."
                        ),
                    )
                )

        return anomalies

    @staticmethod
    def _severity_from_zscore(zscore: float) -> str:
        if zscore >= 3:
            return "high"
        if zscore >= 2.5:
            return "medium"
        return "low"

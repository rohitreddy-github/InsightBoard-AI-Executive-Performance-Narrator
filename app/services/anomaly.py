import math

import pandas as pd

from app.models.schemas import AnomalyDataPoint, AnomalyInsight, MetricSnapshot
from app.services.ingestion import DatasetBundle


class AnomalyDetector:
    """
    deterministic anomaly detection using rolling z-score analysis.
    Flags values >2 or <-2 standard deviations from rolling mean.
    Returns structured list of anomalous points with dates and deviation percentages.
    """

    def __init__(self, zscore_threshold: float = 2.0, change_threshold: float = 0.1, rolling_window: int = 3) -> None:
        self.zscore_threshold = zscore_threshold
        self.change_threshold = change_threshold
        self.rolling_window = rolling_window

    def detect(self, dataset: DatasetBundle, snapshots: list[MetricSnapshot]) -> list[AnomalyInsight]:
        """
        Detect anomalies using rolling window z-score analysis.

        For each metric, computes rolling mean and std over a window,
        then flags all points where |zscore| >= threshold.

        Returns structured anomalies with precise dates and deviation metrics.
        """
        snapshot_map = {snapshot.metric: snapshot for snapshot in snapshots}
        anomalies: list[AnomalyInsight] = []

        for metric in dataset.metric_columns:
            series = dataset.frame[metric].dropna().astype(float)
            dates = pd.to_datetime(dataset.frame["date"]).dropna()

            if len(series) < self.rolling_window + 1:
                continue

            snapshot = snapshot_map.get(metric)
            if snapshot is None:
                continue

            # Calculate rolling statistics
            rolling_mean = series.rolling(window=self.rolling_window, center=False).mean()
            rolling_std = series.rolling(window=self.rolling_window, center=False).std()

            # Calculate z-scores for all points
            zscores = pd.Series(
                [
                    0.0 if math.isclose(rolling_std.iloc[i], 0.0)
                    else (series.iloc[i] - rolling_mean.iloc[i]) / rolling_std.iloc[i]
                    for i in range(len(series))
                ],
                index=series.index
            )

            # Identify anomalous points (|zscore| >= threshold)
            anomalous_mask = abs(zscores) >= self.zscore_threshold
            anomalous_indices = anomalous_mask[anomalous_mask].index.tolist()

            if not anomalous_indices:
                continue

            # Build detailed anomaly data points
            anomalous_points: list[AnomalyDataPoint] = []
            for idx in anomalous_indices:
                if pd.isna(rolling_mean.iloc[idx]) or pd.isna(rolling_std.iloc[idx]):
                    continue

                value = float(series.iloc[idx])
                rm = float(rolling_mean.iloc[idx])
                rs = float(rolling_std.iloc[idx])
                z = float(zscores.iloc[idx])
                deviation_pct = abs(z) * 100  # Deviation as percentage of std

                anomalous_points.append(
                    AnomalyDataPoint(
                        date=dates.iloc[idx],
                        value=value,
                        rolling_mean=rm,
                        rolling_std=rs,
                        zscore=z,
                        deviation_percent=deviation_pct,
                    )
                )

            if anomalous_points:
                # Determine overall severity from max zscore
                max_zscore = max(abs(ap.zscore) for ap in anomalous_points)
                latest_value = float(series.iloc[-1])
                mean_baseline = float(rolling_mean.iloc[-1]) if not pd.isna(rolling_mean.iloc[-1]) else float(series.mean())

                anomalies.append(
                    AnomalyInsight(
                        metric=metric,
                        severity=self._severity_from_zscore(max_zscore),
                        latest_value=latest_value,
                        baseline_value=mean_baseline,
                        reason=(
                            f"Detected {len(anomalous_points)} anomalous point(s) with z-scores exceeding "
                            f"plus/minus {self.zscore_threshold}. Maximum deviation: {max_zscore:.2f} standard deviations."
                        ),
                        anomalous_points=anomalous_points,
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

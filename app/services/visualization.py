import base64
import io
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

from app.models.schemas import AnomalyInsight, MetricSnapshot
from app.services.ingestion import DatasetBundle


class DataVisualizationService:
    """
    Generates clean, high-contrast Matplotlib charts with anomaly highlights.
    Outputs are saved to in-memory BytesIO buffers and encoded as Base64.
    Optimized for multimodal LLM vision understanding.
    """

    def __init__(self, figsize: tuple[int, int] = (14, 8), dpi: int = 100):
        """
        Args:
            figsize: Figure size (width, height) in inches
            dpi: Dots per inch for rendering quality
        """
        self.figsize = figsize
        self.dpi = dpi
        plt.style.use("seaborn-v0_8-darkgrid")

    def generate_anomaly_chart(
        self,
        dataset: DatasetBundle,
        anomaly: AnomalyInsight,
    ) -> tuple[bytes, str]:
        """
        Generate a chart for a single metric with anomalies highlighted.

        Args:
            dataset: Complete dataset with all metric columns and dates
            anomaly: Anomaly insight containing detected anomalous points

        Returns:
            (image_bytes, base64_encoded_string)
        """
        metric_name = anomaly.metric
        if metric_name not in dataset.frame.columns:
            raise ValueError(f"Metric '{metric_name}' not found in dataset")

        # Extract time series data
        dates = pd.to_datetime(dataset.frame["date"])
        values = dataset.frame[metric_name].astype(float)

        # Create figure
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        # Plot main trend line
        ax.plot(
            dates,
            values,
            linewidth=2.5,
            color="#1f77b4",
            label="Actual Value",
            marker="o",
            markersize=5,
            alpha=0.8,
        )

        # Plot rolling mean baseline
        if anomaly.anomalous_points:
            rolling_means = [pt.rolling_mean for pt in anomaly.anomalous_points]
            if rolling_means:
                mean_baseline = sum(rolling_means) / len(rolling_means)
                ax.axhline(
                    y=mean_baseline,
                    color="#2ca02c",
                    linestyle="--",
                    linewidth=2,
                    label=f"Rolling Baseline (Mean: {mean_baseline:,.0f})",
                    alpha=0.7,
                )

        # Highlight anomalous points with color coding by severity
        for point in anomaly.anomalous_points:
            point_date = pd.to_datetime(point.date)
            # Find matching value in the time series
            idx = dates[dates == point_date].index
            if len(idx) > 0:
                actual_idx = idx[0]
                actual_value = values.iloc[actual_idx]

                # Color by severity
                if abs(point.zscore) >= 3:
                    color = "#d62728"  # Red for high
                    marker = "X"
                    size = 200
                elif abs(point.zscore) >= 2.5:
                    color = "#ff7f0e"  # Orange for medium
                    marker = "s"
                    size = 120
                else:
                    color = "#ffd700"  # Gold for low
                    marker = "D"
                    size = 80

                ax.scatter(
                    point_date,
                    actual_value,
                    color=color,
                    marker=marker,
                    s=size,
                    edgecolors="black",
                    linewidth=1.5,
                    zorder=5,
                    alpha=0.9,
                )

        # Format axes
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45, ha="right")

        # Labels and title
        ax.set_xlabel("Date", fontsize=12, fontweight="bold")
        ax.set_ylabel("Value", fontsize=12, fontweight="bold")
        ax.set_title(
            f"Metric: {metric_name} | Severity: {anomaly.severity.upper()} | Anomalies: {len(anomaly.anomalous_points)}",
            fontsize=14,
            fontweight="bold",
            pad=20,
        )

        # Legend with custom labels
        legend_elements = [
            plt.Line2D([0], [0], color="#1f77b4", linewidth=2.5, marker="o", markersize=7, label="Actual Value"),
            plt.Line2D([0], [0], color="#2ca02c", linestyle="--", linewidth=2, label="Rolling Baseline"),
            plt.scatter([], [], marker="X", s=200, color="#d62728", edgecolors="black", linewidth=1.5, label="High Severity (|z| ≥ 3.0)"),
            plt.scatter([], [], marker="s", s=120, color="#ff7f0e", edgecolors="black", linewidth=1.5, label="Medium Severity (|z| ≥ 2.5)"),
            plt.scatter([], [], marker="D", s=80, color="#ffd700", edgecolors="black", linewidth=1.5, label="Low Severity (|z| ≥ 2.0)"),
        ]
        ax.legend(handles=legend_elements, loc="best", fontsize=10, framealpha=0.95)

        # Grid for readability
        ax.grid(True, alpha=0.3, linestyle=":", linewidth=0.8)

        # Tight layout to prevent label cutoff
        plt.tight_layout()

        # Save to BytesIO buffer
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=self.dpi, bbox_inches="tight")
        buffer.seek(0)
        image_bytes = buffer.getvalue()
        plt.close(fig)

        # Encode to Base64
        base64_string = base64.b64encode(image_bytes).decode("utf-8")

        return image_bytes, base64_string

    def generate_multiplot_dashboard(
        self,
        dataset: DatasetBundle,
        anomalies: list[AnomalyInsight],
        max_metrics: int = 4,
    ) -> tuple[bytes, str]:
        """
        Generate a multi-metric dashboard with up to max_metrics subplots.

        Args:
            dataset: Complete dataset
            anomalies: List of anomaly insights
            max_metrics: Maximum number of metrics to display (creates subplots)

        Returns:
            (image_bytes, base64_encoded_string)
        """
        # Limit to max_metrics
        anomalies_to_plot = anomalies[:max_metrics]
        if not anomalies_to_plot:
            raise ValueError("No anomalies provided to visualize")

        # Calculate grid size
        n_plots = len(anomalies_to_plot)
        n_cols = min(2, n_plots)
        n_rows = (n_plots + n_cols - 1) // n_cols

        fig, axes = plt.subplots(
            n_rows,
            n_cols,
            figsize=(self.figsize[0], self.figsize[1] * n_rows / 2),
            dpi=self.dpi,
        )

        # Ensure axes is always iterable (even for single plot)
        if n_plots == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        dates = pd.to_datetime(dataset.frame["date"])

        for idx, anomaly in enumerate(anomalies_to_plot):
            ax = axes[idx]
            metric_name = anomaly.metric

            if metric_name not in dataset.frame.columns:
                ax.text(0.5, 0.5, f"Metric '{metric_name}' not found", ha="center", va="center")
                continue

            values = dataset.frame[metric_name].astype(float)

            # Plot trend
            ax.plot(
                dates,
                values,
                linewidth=2,
                color="#1f77b4",
                marker="o",
                markersize=4,
                alpha=0.8,
            )

            # Highlight anomalies
            for point in anomaly.anomalous_points:
                point_date = pd.to_datetime(point.date)
                matching_idx = dates[dates == point_date].index
                if len(matching_idx) > 0:
                    actual_idx = matching_idx[0]
                    actual_value = values.iloc[actual_idx]

                    if abs(point.zscore) >= 3:
                        color = "#d62728"
                    elif abs(point.zscore) >= 2.5:
                        color = "#ff7f0e"
                    else:
                        color = "#ffd700"

                    ax.scatter(point_date, actual_value, color=color, s=100, edgecolors="black", zorder=5)

            # Format
            ax.set_title(f"{metric_name} ({anomaly.severity.upper()})", fontsize=11, fontweight="bold")
            ax.set_xlabel("Date", fontsize=9)
            ax.set_ylabel("Value", fontsize=9)
            ax.tick_params(axis="both", labelsize=8)
            ax.grid(True, alpha=0.3, linestyle=":", linewidth=0.8)
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # Hide unused subplots
        for idx in range(len(anomalies_to_plot), len(axes)):
            axes[idx].axis("off")

        fig.suptitle("Anomaly Detection Dashboard", fontsize=16, fontweight="bold", y=0.995)
        plt.tight_layout()

        # Save to buffer
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=self.dpi, bbox_inches="tight")
        buffer.seek(0)
        image_bytes = buffer.getvalue()
        plt.close(fig)

        # Encode to Base64
        base64_string = base64.b64encode(image_bytes).decode("utf-8")

        return image_bytes, base64_string

    def generate_comparison_chart(
        self,
        dataset: DatasetBundle,
        metric_snapshots: list[MetricSnapshot],
        max_metrics: int = 6,
    ) -> tuple[bytes, str]:
        """
        Generate a bar chart comparing latest values across multiple metrics.

        Args:
            dataset: Complete dataset
            metric_snapshots: List of metric snapshots with latest values
            max_metrics: Maximum number of metrics to display

        Returns:
            (image_bytes, base64_encoded_string)
        """
        snapshots_to_plot = metric_snapshots[:max_metrics]
        if not snapshots_to_plot:
            raise ValueError("No metric snapshots provided")

        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        metrics = [s.metric for s in snapshots_to_plot]
        latest_values = [s.latest_value for s in snapshots_to_plot]
        trend_colors = {
            "up": "#2ca02c",      # Green
            "down": "#d62728",    # Red
            "flat": "#1f77b4",    # Blue
        }
        colors = [trend_colors[s.trend_direction] for s in snapshots_to_plot]

        # Create bar chart
        bars = ax.bar(metrics, latest_values, color=colors, edgecolor="black", linewidth=1.5, alpha=0.8)

        # Add value labels on top of bars
        for bar, value in zip(bars, latest_values):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{value:,.0f}",
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

        # Labels and title
        ax.set_xlabel("Metric", fontsize=12, fontweight="bold")
        ax.set_ylabel("Latest Value", fontsize=12, fontweight="bold")
        ax.set_title("Latest Metric Values Comparison", fontsize=14, fontweight="bold", pad=20)

        # Legend for trend colors
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor="#2ca02c", edgecolor="black", label="Uptrend"),
            Patch(facecolor="#d62728", edgecolor="black", label="Downtrend"),
            Patch(facecolor="#1f77b4", edgecolor="black", label="Flat"),
        ]
        ax.legend(handles=legend_elements, loc="best", fontsize=10)

        plt.xticks(rotation=45, ha="right")
        ax.grid(True, alpha=0.3, axis="y", linestyle=":", linewidth=0.8)
        plt.tight_layout()

        # Save to buffer
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=self.dpi, bbox_inches="tight")
        buffer.seek(0)
        image_bytes = buffer.getvalue()
        plt.close(fig)

        # Encode to Base64
        base64_string = base64.b64encode(image_bytes).decode("utf-8")

        return image_bytes, base64_string

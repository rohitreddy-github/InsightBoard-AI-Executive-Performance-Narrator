from app.models.schemas import AnomalyInsight, ChartExplanation, MetricSnapshot


class ChartExplainer:
    def explain(
        self,
        metric_snapshots: list[MetricSnapshot],
        anomalies: list[AnomalyInsight],
        chart_image_bytes: bytes | None,
    ) -> ChartExplanation:
        top_metrics = ", ".join(snapshot.metric for snapshot in metric_snapshots[:3]) or "available KPIs"

        if chart_image_bytes:
            summary = (
                "A chart image was provided. The multimodal explanation hook is scaffolded, and the "
                f"current heuristic summary aligns the visual narrative with the strongest KPI movement in {top_metrics}. "
                f"Detected anomaly count: {len(anomalies)}."
            )
            return ChartExplanation(source="multimodal-placeholder", summary=summary)

        summary = (
            "No chart image was uploaded, so the explanation is data-driven. "
            f"The strongest narrative centers on {top_metrics}, with {len(anomalies)} anomaly signal(s) surfaced "
            "from the structured KPI time series."
        )
        return ChartExplanation(source="heuristic", summary=summary)

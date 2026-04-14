import base64
from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.schemas import MissingValueStrategy, ReportResponse, TimeAggregation
from app.prompts.system_prompts import PersonaRole
from app.services.analytics import KPIAnalyzer
from app.services.anomaly import AnomalyDetector
from app.services.chart_explainer import ChartExplainer
from app.services.ingestion import CSVIngestionService
from app.services.llm import build_llm_client
from app.services.narrative import NarrativeGenerator
from app.services.visualization import DataVisualizationService


class ReportPipeline:
    def __init__(
        self,
        ingestion_service: CSVIngestionService,
        analyzer: KPIAnalyzer,
        anomaly_detector: AnomalyDetector,
        chart_explainer: ChartExplainer,
        narrative_generator: NarrativeGenerator,
        visualization_service: DataVisualizationService | None = None,
    ) -> None:
        self.ingestion_service = ingestion_service
        self.analyzer = analyzer
        self.anomaly_detector = anomaly_detector
        self.chart_explainer = chart_explainer
        self.narrative_generator = narrative_generator
        self.visualization_service = visualization_service or DataVisualizationService()

    def generate_report(
        self,
        report_title: str,
        csv_bytes: bytes,
        source_name: str,
        aggregation_granularity: TimeAggregation = "monthly",
        missing_value_strategy: MissingValueStrategy = "forward_fill",
        chart_image_bytes: bytes | None = None,
        chart_image_mime_type: str | None = None,
        persona: PersonaRole = PersonaRole.CFO,
    ) -> ReportResponse:
        dataset = self.ingestion_service.load_csv(
            csv_bytes,
            aggregation_granularity=aggregation_granularity,
            missing_value_strategy=missing_value_strategy,
        )
        metric_snapshots = self.analyzer.build_metric_snapshots(dataset)
        anomalies = self.anomaly_detector.detect(dataset, metric_snapshots)

        prompt_chart_image_bytes = chart_image_bytes
        prompt_chart_base64 = (
            base64.b64encode(chart_image_bytes).decode("utf-8")
            if chart_image_bytes is not None
            else None
        )
        prompt_chart_mime_type = chart_image_mime_type or "image/png"
        if prompt_chart_image_bytes is None and anomalies:
            try:
                prompt_chart_image_bytes, prompt_chart_base64 = self.visualization_service.generate_multiplot_dashboard(
                    dataset=dataset,
                    anomalies=anomalies,
                )
                prompt_chart_mime_type = "image/png"
            except ValueError:
                prompt_chart_image_bytes = None
                prompt_chart_base64 = None

        chart_explanation = self.chart_explainer.explain(
            metric_snapshots=metric_snapshots,
            anomalies=anomalies,
            chart_image_bytes=prompt_chart_image_bytes,
        )
        narrative = self.narrative_generator.generate(
            report_title=report_title,
            metric_snapshots=metric_snapshots,
            anomalies=anomalies,
            chart_explanation=chart_explanation,
            persona=persona,
            chart_base64=prompt_chart_base64,
            chart_mime_type=prompt_chart_mime_type,
            records_analyzed=dataset.record_count,
            periods_analyzed=dataset.period_count,
            date_range_start=dataset.frame["date"].min().strftime("%Y-%m-%d"),
            date_range_end=dataset.frame["date"].max().strftime("%Y-%m-%d"),
        )

        return ReportResponse(
            report_title=report_title,
            generated_at=datetime.now(timezone.utc),
            source_name=source_name,
            records_analyzed=dataset.record_count,
            periods_analyzed=dataset.period_count,
            date_column=dataset.date_column,
            preprocessing_summary=dataset.preprocessing_summary,
            metric_snapshots=metric_snapshots,
            executive_summary=narrative.summary,
            trend_narrative=narrative.trend_narrative,
            anomaly_commentary=narrative.anomaly_commentary,
            chart_explanation=chart_explanation,
            recommended_actions=narrative.recommended_actions,
        )


def build_report_pipeline() -> ReportPipeline:
    settings = get_settings()

    return ReportPipeline(
        ingestion_service=CSVIngestionService(),
        analyzer=KPIAnalyzer(),
        anomaly_detector=AnomalyDetector(
            zscore_threshold=settings.anomaly_zscore_threshold,
            change_threshold=settings.latest_change_alert_threshold,
        ),
        chart_explainer=ChartExplainer(),
        narrative_generator=NarrativeGenerator(llm_client=build_llm_client(settings)),
        visualization_service=DataVisualizationService(),
    )

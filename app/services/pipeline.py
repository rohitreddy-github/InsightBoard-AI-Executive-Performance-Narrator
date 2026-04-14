from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.schemas import MissingValueStrategy, ReportResponse, TimeAggregation
from app.services.analytics import KPIAnalyzer
from app.services.anomaly import AnomalyDetector
from app.services.chart_explainer import ChartExplainer
from app.services.ingestion import CSVIngestionService
from app.services.llm import MockLLMClient
from app.services.narrative import NarrativeGenerator


class ReportPipeline:
    def __init__(
        self,
        ingestion_service: CSVIngestionService,
        analyzer: KPIAnalyzer,
        anomaly_detector: AnomalyDetector,
        chart_explainer: ChartExplainer,
        narrative_generator: NarrativeGenerator,
    ) -> None:
        self.ingestion_service = ingestion_service
        self.analyzer = analyzer
        self.anomaly_detector = anomaly_detector
        self.chart_explainer = chart_explainer
        self.narrative_generator = narrative_generator

    def generate_report(
        self,
        report_title: str,
        csv_bytes: bytes,
        source_name: str,
        aggregation_granularity: TimeAggregation = "monthly",
        missing_value_strategy: MissingValueStrategy = "forward_fill",
        chart_image_bytes: bytes | None = None,
    ) -> ReportResponse:
        dataset = self.ingestion_service.load_csv(
            csv_bytes,
            aggregation_granularity=aggregation_granularity,
            missing_value_strategy=missing_value_strategy,
        )
        metric_snapshots = self.analyzer.build_metric_snapshots(dataset)
        anomalies = self.anomaly_detector.detect(dataset, metric_snapshots)
        chart_explanation = self.chart_explainer.explain(
            metric_snapshots=metric_snapshots,
            anomalies=anomalies,
            chart_image_bytes=chart_image_bytes,
        )
        narrative = self.narrative_generator.generate(
            report_title=report_title,
            metric_snapshots=metric_snapshots,
            anomalies=anomalies,
            chart_explanation=chart_explanation,
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
        narrative_generator=NarrativeGenerator(llm_client=MockLLMClient()),
    )

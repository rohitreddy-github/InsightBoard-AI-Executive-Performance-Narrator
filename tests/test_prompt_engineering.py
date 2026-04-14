from datetime import date

from app.models.schemas import AnomalyDataPoint, AnomalyInsight, ChartExplanation, MetricSnapshot
from app.prompts.system_prompts import PersonaRole
from app.services.analytics import KPIAnalyzer
from app.services.anomaly import AnomalyDetector
from app.services.chart_explainer import ChartExplainer
from app.services.ingestion import CSVIngestionService
from app.services.llm import StructuredPrompt
from app.services.narrative import NarrativeGenerator
from app.services.pipeline import ReportPipeline
from app.services.prompt_engineering import PromptAssembler, PromptChainExecutor, PromptStep
from app.services.visualization import DataVisualizationService


class RecordingLLMClient:
    def __init__(self) -> None:
        self.last_prompt: StructuredPrompt | None = None
        self.last_system_prompt: str | None = None
        self.last_context: dict | None = None

    def generate_sections(
        self,
        report_title: str,
        context: dict,
        fallback,
        prompt: StructuredPrompt | None = None,
        system_prompt: str | None = None,
    ):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        self.last_context = context
        return fallback


def build_prompt_fixtures() -> tuple[list[MetricSnapshot], list[AnomalyInsight], ChartExplanation]:
    metric_snapshots = [
        MetricSnapshot(
            metric="revenue",
            latest_value=520000.0,
            previous_value=500000.0,
            absolute_change=20000.0,
            percent_change=0.04,
            mean_value=487500.0,
            min_value=450000.0,
            max_value=520000.0,
            trend_direction="up",
        ),
        MetricSnapshot(
            metric="churn_rate",
            latest_value=0.08,
            previous_value=0.06,
            absolute_change=0.02,
            percent_change=0.3333,
            mean_value=0.055,
            min_value=0.03,
            max_value=0.08,
            trend_direction="up",
        ),
    ]
    anomalies = [
        AnomalyInsight(
            metric="revenue",
            severity="high",
            latest_value=520000.0,
            baseline_value=480000.0,
            reason="Detected 1 anomalous point with z-scores exceeding +/- 2.0 standard deviations.",
            anomalous_points=[
                AnomalyDataPoint(
                    date=date(2026, 3, 1),
                    value=520000.0,
                    rolling_mean=480000.0,
                    rolling_std=15000.0,
                    zscore=2.67,
                    deviation_percent=8.33,
                )
            ],
        )
    ]
    chart_explanation = ChartExplanation(
        source="multimodal-placeholder",
        summary="A generated dashboard highlights the revenue spike against its rolling baseline.",
    )
    return metric_snapshots, anomalies, chart_explanation


def test_prompt_assembler_includes_dynamic_kpi_and_anomaly_context() -> None:
    metric_snapshots, anomalies, chart_explanation = build_prompt_fixtures()
    assembler = PromptAssembler(persona=PersonaRole.CFO)

    assembly = assembler.assemble(
        anomalies=anomalies,
        metric_snapshots=metric_snapshots,
        report_title="Board KPI Summary",
        records_analyzed=36,
        periods_analyzed=6,
        chart_base64="ZmFrZS1jaGFydA==",
        chart_explanation=chart_explanation,
        date_range_start="2025-10-01",
        date_range_end="2026-03-01",
    )

    assert "Chief Financial Officer" in assembly.system_prompt
    assert "<report_metadata>" in assembly.user_prompt
    assert '<statistical_summary metric_count="2">' in assembly.user_prompt
    assert '<anomalies count="1" total_points="1">' in assembly.user_prompt
    assert "<chart_image_base64>" in assembly.user_prompt
    assert "ZmFrZS1jaGFydA==" in assembly.user_prompt
    assert "revenue" in assembly.user_prompt
    assert "zscore=2.67" in assembly.user_prompt
    assert "2025-10-01" in assembly.user_prompt
    assert "A generated dashboard highlights the revenue spike" in assembly.context_sections["chart"]


def test_prompt_chain_executor_replaces_initial_context_and_previous_outputs() -> None:
    executor = PromptChainExecutor(default_persona=PersonaRole.CFO)
    steps = [
        PromptStep(
            name="summarize",
            system_instruction="Summarize the KPI.",
            user_prompt_template="Summarize {metric_name}.",
        ),
        PromptStep(
            name="recommend",
            system_instruction="Recommend an action.",
            user_prompt_template="Use prior work: {previous_summarize}",
        ),
    ]

    results = executor.execute_chain(steps=steps, initial_context={"metric_name": "revenue"})

    assert results["summarize"]["user"] == "Summarize revenue."
    assert results["recommend"]["user"] == "Use prior work: Summarize revenue."


def test_narrative_generator_passes_structured_prompt_to_llm() -> None:
    metric_snapshots, anomalies, chart_explanation = build_prompt_fixtures()
    llm_client = RecordingLLMClient()
    generator = NarrativeGenerator(llm_client=llm_client)

    generator.generate(
        report_title="Executive KPI Review",
        metric_snapshots=metric_snapshots,
        anomalies=anomalies,
        chart_explanation=chart_explanation,
        persona=PersonaRole.CRO,
        chart_base64="YWJjZA==",
        records_analyzed=48,
        periods_analyzed=8,
        date_range_start="2025-08-01",
        date_range_end="2026-03-01",
    )

    assert llm_client.last_prompt is not None
    assert "Chief Revenue Officer" in llm_client.last_prompt.system_prompt
    assert "YWJjZA==" in llm_client.last_prompt.user_prompt
    assert llm_client.last_context is not None
    assert llm_client.last_context["report_metadata"]["records_analyzed"] == 48
    assert llm_client.last_context["prompt_context"]["chart"].startswith("<chart_context")


def test_report_pipeline_passes_generated_chart_and_persona_into_prompt(sample_csv_bytes: bytes) -> None:
    llm_client = RecordingLLMClient()
    pipeline = ReportPipeline(
        ingestion_service=CSVIngestionService(),
        analyzer=KPIAnalyzer(),
        anomaly_detector=AnomalyDetector(zscore_threshold=2.0, change_threshold=0.15, rolling_window=3),
        chart_explainer=ChartExplainer(),
        narrative_generator=NarrativeGenerator(llm_client=llm_client),
        visualization_service=DataVisualizationService(),
    )

    pipeline.generate_report(
        report_title="Sales Leadership Review",
        csv_bytes=sample_csv_bytes,
        source_name="monthly_kpis.csv",
        persona=PersonaRole.CRO,
    )

    assert llm_client.last_prompt is not None
    assert "Chief Revenue Officer" in llm_client.last_prompt.system_prompt
    assert "<chart_context" in llm_client.last_prompt.user_prompt
    assert llm_client.last_context is not None
    assert llm_client.last_context["report_metadata"]["persona"] == "cro"

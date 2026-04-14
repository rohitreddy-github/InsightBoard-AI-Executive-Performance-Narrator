from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StringConstraints
from typing_extensions import Annotated


class HealthResponse(BaseModel):
    status: str


MetricName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
TimeAggregation = Literal["weekly", "monthly"]
MissingValueStrategy = Literal["drop", "forward_fill", "interpolate"]


class KPIRecordInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    date: str | date
    metric_name: MetricName
    value: FiniteFloat | None = None


class CSVColumnContract(BaseModel):
    name: str
    data_type: str
    required: bool
    description: str


class InputDataContract(BaseModel):
    format: Literal["long"]
    description: str
    required_columns: list[CSVColumnContract]
    allowed_columns: list[str]
    example_row: KPIRecordInput
    validation_rules: list[str]


class WorkflowStage(BaseModel):
    step: int
    name: str
    input_artifacts: list[str]
    output_artifacts: list[str]
    purpose: str


class WorkflowDefinition(BaseModel):
    name: str
    stages: list[WorkflowStage]


class PreprocessingSummary(BaseModel):
    aggregation_granularity: TimeAggregation
    missing_value_strategy: MissingValueStrategy
    rows_received: int
    exact_duplicate_rows_removed: int
    date_metric_duplicates_collapsed: int
    missing_values_detected: int
    missing_values_imputed: int
    output_periods_generated: int


class MetricSnapshot(BaseModel):
    metric: str
    latest_value: float
    previous_value: float | None = None
    absolute_change: float | None = None
    percent_change: float | None = None
    mean_value: float
    min_value: float
    max_value: float
    trend_direction: Literal["up", "down", "flat"]


class AnomalyInsight(BaseModel):
    metric: str
    severity: Literal["low", "medium", "high"]
    latest_value: float
    baseline_value: float
    reason: str


class ChartExplanation(BaseModel):
    source: Literal["heuristic", "multimodal-placeholder"]
    summary: str


class NarrativeSections(BaseModel):
    summary: str
    trend_narrative: list[str] = Field(default_factory=list)
    anomaly_commentary: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class ReportResponse(BaseModel):
    report_title: str
    generated_at: datetime
    source_name: str
    records_analyzed: int
    periods_analyzed: int
    date_column: str | None = None
    preprocessing_summary: PreprocessingSummary
    metric_snapshots: list[MetricSnapshot]
    executive_summary: str
    trend_narrative: list[str]
    anomaly_commentary: list[str]
    chart_explanation: ChartExplanation
    recommended_actions: list[str]

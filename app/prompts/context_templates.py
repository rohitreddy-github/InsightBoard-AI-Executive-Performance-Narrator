"""
Phase 5: Context Format Templates

Provides structured formatting for KPI context with clear XML/Markdown delimiters.
Designed for optimal LLM parsing and human readability.
"""

from datetime import datetime, timezone

from app.models.schemas import (
    AnomalyDataPoint,
    AnomalyInsight,
    ChartExplanation,
    MetricSnapshot,
)


class ContextFormatter:
    """Formats KPI analytics context into structured markdown/XML for LLM consumption."""

    CHART_CONTEXT_INSTRUCTION = (
        "If a vision-capable model is available, decode the Base64 payload and inspect the PNG directly. "
        "Otherwise, rely on the textual chart summary and anomaly evidence."
    )

    # ========================================================================
    # Metric Formatting
    # ========================================================================

    @staticmethod
    def format_metric_snapshot(snapshot: MetricSnapshot) -> str:
        """Format a single metric snapshot into a concise statistical summary."""
        trend_labels = {
            "up": "[UP]",
            "down": "[DOWN]",
            "flat": "[FLAT]",
        }
        trend_label = trend_labels.get(snapshot.trend_direction, "[FLAT]")

        previous_value = (
            f"{snapshot.previous_value:,.2f}"
            if snapshot.previous_value is not None
            else "N/A"
        )
        absolute_change = (
            f"{snapshot.absolute_change:+,.2f}"
            if snapshot.absolute_change is not None
            else "N/A"
        )
        percent_change = (
            f"{snapshot.percent_change * 100:+.1f}%"
            if snapshot.percent_change is not None
            else "N/A"
        )

        return f"""### {snapshot.metric}
- Direction: {trend_label} {snapshot.trend_direction.upper()}
- Latest Value: {snapshot.latest_value:,.2f}
- Previous Value: {previous_value}
- Absolute Change: {absolute_change}
- Percent Change: {percent_change}
- Mean: {snapshot.mean_value:,.2f}
- Min / Max: {snapshot.min_value:,.2f} / {snapshot.max_value:,.2f}"""

    @staticmethod
    def format_statistical_summary(snapshots: list[MetricSnapshot]) -> str:
        """Format all metric snapshots into a statistical summary section."""
        if not snapshots:
            return """<statistical_summary metric_count="0">
No KPI snapshots were available after preprocessing.
</statistical_summary>"""

        metrics_text = "\n\n".join(
            ContextFormatter.format_metric_snapshot(snapshot)
            for snapshot in snapshots
        )

        return f"""<statistical_summary metric_count="{len(snapshots)}">
{metrics_text}
</statistical_summary>"""

    # ========================================================================
    # Anomaly Formatting
    # ========================================================================

    @staticmethod
    def format_anomaly_point(point: AnomalyDataPoint) -> str:
        """Format a single anomalous data point."""
        date_str = point.date.strftime("%Y-%m-%d")
        direction = "above" if point.deviation_percent >= 0 else "below"
        return (
            f"- {date_str}: value={point.value:,.2f}, rolling_mean={point.rolling_mean:,.2f}, "
            f"rolling_std={point.rolling_std:,.2f}, zscore={point.zscore:.2f}, "
            f"deviation={abs(point.deviation_percent):.1f}% {direction} baseline"
        )

    @staticmethod
    def format_anomaly_insight(anomaly: AnomalyInsight) -> str:
        """Format a complete anomaly insight with all contextual details."""
        points_text = "\n".join(
            ContextFormatter.format_anomaly_point(point)
            for point in anomaly.anomalous_points
        ) if anomaly.anomalous_points else "- No anomalous points recorded"

        baseline_change = (
            ((anomaly.latest_value - anomaly.baseline_value) / anomaly.baseline_value * 100)
            if anomaly.baseline_value
            else 0.0
        )

        return f"""<anomaly metric="{anomaly.metric}" severity="{anomaly.severity}" anomalous_points="{len(anomaly.anomalous_points)}">
<latest_value>{anomaly.latest_value:,.2f}</latest_value>
<baseline_value>{anomaly.baseline_value:,.2f}</baseline_value>
<latest_vs_baseline_percent>{baseline_change:+.1f}%</latest_vs_baseline_percent>
<reason>{anomaly.reason}</reason>
<proved_points>
{points_text}
</proved_points>
</anomaly>"""

    @staticmethod
    def format_anomalies_section(anomalies: list[AnomalyInsight]) -> str:
        """Format all anomalies into a structured section."""
        if not anomalies:
            return """<anomalies count="0">
No KPI values exceeded the configured anomaly threshold in this reporting period.
</anomalies>"""

        anomalies_text = "\n\n".join(
            ContextFormatter.format_anomaly_insight(anomaly)
            for anomaly in anomalies
        )

        severity_counts = {
            "high": len([a for a in anomalies if a.severity == "high"]),
            "medium": len([a for a in anomalies if a.severity == "medium"]),
            "low": len([a for a in anomalies if a.severity == "low"]),
        }
        total_anomalous_points = sum(len(a.anomalous_points) for a in anomalies)

        return f"""<anomalies count="{len(anomalies)}" total_points="{total_anomalous_points}">
<severity_summary>
- HIGH: {severity_counts["high"]}
- MEDIUM: {severity_counts["medium"]}
- LOW: {severity_counts["low"]}
</severity_summary>

{anomalies_text}
</anomalies>"""

    # ========================================================================
    # Chart Context Formatting
    # ========================================================================

    @staticmethod
    def format_chart_context(
        chart_base64: str | None = None,
        chart_explanation: ChartExplanation | None = None,
    ) -> str:
        """Format chart explanation and image payload context."""
        if chart_base64:
            chart_summary = (
                chart_explanation.summary
                if chart_explanation is not None
                else "A dashboard visualization is available for multimodal inspection."
            )
            chart_source = (
                chart_explanation.source
                if chart_explanation is not None
                else "multimodal-placeholder"
            )

            return f"""<chart_context source="{chart_source}" has_image="true" mime_type="image/png" encoding="base64">
<summary>{chart_summary}</summary>
<usage_instruction>{ContextFormatter.CHART_CONTEXT_INSTRUCTION}</usage_instruction>
<image_bytes_estimate>{len(chart_base64) // 4 * 3}</image_bytes_estimate>
<chart_image_base64>
{chart_base64}
</chart_image_base64>
</chart_context>"""

        if chart_explanation is not None:
            return f"""<chart_context source="{chart_explanation.source}" has_image="false">
<summary>{chart_explanation.summary}</summary>
<usage_instruction>{ContextFormatter.CHART_CONTEXT_INSTRUCTION}</usage_instruction>
</chart_context>"""

        return f"""<chart_context source="none" has_image="false">
<summary>No chart image was provided or generated for this report.</summary>
<usage_instruction>{ContextFormatter.CHART_CONTEXT_INSTRUCTION}</usage_instruction>
</chart_context>"""

    # ========================================================================
    # Metadata Formatting
    # ========================================================================

    @staticmethod
    def format_metadata(
        report_title: str,
        records_analyzed: int,
        periods_analyzed: int,
        date_range_start: str = "Unknown",
        date_range_end: str = "Unknown",
    ) -> str:
        """Format report metadata section."""
        timestamp = datetime.now(timezone.utc).isoformat()
        return f"""<report_metadata>
<report_title>{report_title}</report_title>
<analysis_period start="{date_range_start}" end="{date_range_end}" periods="{periods_analyzed}" />
<records_analyzed>{records_analyzed}</records_analyzed>
<generation_timestamp>{timestamp}</generation_timestamp>
<analysis_method>Deterministic rolling z-score anomaly detection plus aggregate KPI trend statistics</analysis_method>
</report_metadata>"""

    # ========================================================================
    # Complete Payload Assembly
    # ========================================================================

    @staticmethod
    def build_complete_context(
        anomalies: list[AnomalyInsight],
        metric_snapshots: list[MetricSnapshot],
        report_title: str,
        records_analyzed: int,
        periods_analyzed: int,
        chart_base64: str | None = None,
        chart_explanation: ChartExplanation | None = None,
        date_range_start: str = "Unknown",
        date_range_end: str = "Unknown",
    ) -> str:
        """Assemble complete context payload with all sections."""
        sections = [
            "<kpi_analysis_context>",
            ContextFormatter.format_metadata(
                report_title=report_title,
                records_analyzed=records_analyzed,
                periods_analyzed=periods_analyzed,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
            ),
            ContextFormatter.format_statistical_summary(metric_snapshots),
            ContextFormatter.format_anomalies_section(anomalies),
            ContextFormatter.format_chart_context(
                chart_base64=chart_base64,
                chart_explanation=chart_explanation,
            ),
            "</kpi_analysis_context>",
        ]
        return "\n\n".join(sections)

    @staticmethod
    def build_user_prompt(context: str) -> str:
        """Build a complete user prompt with context and response contract."""
        return f"""Analyze the KPI reporting payload below and produce executive commentary.

Return exactly these sections:
1. Executive Summary: 2-3 sentences for senior leadership.
2. Trend Analysis: 3-5 bullet points grounded in the statistical summary.
3. Anomaly Commentary: 2-4 bullet points explaining the business meaning of mathematically proved anomalies.
4. Recommended Actions: 2-3 concrete next steps.
5. Data Caveats: 1-2 sentences on uncertainty, sparse history, or missing context.

Requirements:
- Use the metadata, statistical summary, anomaly evidence, and chart context together.
- Reference specific metrics, dates, values, and z-scores when discussing anomalies.
- Prioritize business impact over restating every metric.
- Do not invent drivers that are not supported by the payload.

Payload:
{context}"""


# ============================================================================
# Convenience Functions
# ============================================================================

def format_metrics_for_llm(snapshots: list[MetricSnapshot]) -> str:
    """Quick function to format metrics."""
    return ContextFormatter.format_statistical_summary(snapshots)


def format_anomalies_for_llm(anomalies: list[AnomalyInsight]) -> str:
    """Quick function to format anomalies."""
    return ContextFormatter.format_anomalies_section(anomalies)


def build_complete_user_prompt(
    anomalies: list[AnomalyInsight],
    metric_snapshots: list[MetricSnapshot],
    report_title: str,
    records_analyzed: int,
    periods_analyzed: int,
    chart_base64: str | None = None,
    chart_explanation: ChartExplanation | None = None,
    date_range_start: str = "Unknown",
    date_range_end: str = "Unknown",
) -> str:
    """One-function convenience to build complete user prompt."""
    context = ContextFormatter.build_complete_context(
        anomalies=anomalies,
        metric_snapshots=metric_snapshots,
        report_title=report_title,
        records_analyzed=records_analyzed,
        periods_analyzed=periods_analyzed,
        chart_base64=chart_base64,
        chart_explanation=chart_explanation,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )
    return ContextFormatter.build_user_prompt(context)

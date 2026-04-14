from app.models.schemas import AnomalyInsight, ChartExplanation, MetricSnapshot, NarrativeSections
from app.services.llm import LLMClient, StructuredPrompt
from app.services.prompt_engineering import PromptAssembler
from app.prompts.system_prompts import PersonaRole


class NarrativeGenerator:
    def __init__(self, llm_client: LLMClient, default_persona: PersonaRole = PersonaRole.CFO) -> None:
        self.llm_client = llm_client
        self.default_persona = default_persona

    def generate(
        self,
        report_title: str,
        metric_snapshots: list[MetricSnapshot],
        anomalies: list[AnomalyInsight],
        chart_explanation: ChartExplanation,
        persona: PersonaRole | None = None,
        chart_base64: str | None = None,
        chart_mime_type: str = "image/png",
        records_analyzed: int | None = None,
        periods_analyzed: int | None = None,
        date_range_start: str = "Unknown",
        date_range_end: str = "Unknown",
    ) -> NarrativeSections:
        """
        Generate narrative sections with optional persona-specific prompt engineering.

        Args:
            report_title: Title of the report
            metric_snapshots: List of KPI snapshots
            anomalies: List of detected anomalies
            chart_explanation: Chart explanation metadata
            persona: Optional persona for prompt personalization (defaults to CFO)
            chart_base64: Optional base64-encoded chart image
            chart_mime_type: MIME type for the chart image payload
            records_analyzed: Count of source rows analyzed
            periods_analyzed: Count of time buckets analyzed
            date_range_start: Start date of analyzed period
            date_range_end: End date of analyzed period

        Returns:
            NarrativeSections with generated narrative
        """
        persona = persona or self.default_persona
        resolved_records = records_analyzed or len(metric_snapshots)
        resolved_periods = periods_analyzed or len(metric_snapshots)

        # Build fallback narrative (always available)
        up_trends = [snapshot.metric for snapshot in metric_snapshots if snapshot.trend_direction == "up"]
        down_trends = [snapshot.metric for snapshot in metric_snapshots if snapshot.trend_direction == "down"]

        summary_parts = [
            f"{report_title} covers {resolved_periods} reporting period(s) across {len(metric_snapshots)} KPI(s).",
            self._build_summary_line(up_trends, down_trends),
            f"{len(anomalies)} anomaly signal(s) require attention.",
        ]
        summary = " ".join(part for part in summary_parts if part)

        trend_narrative = self._build_trend_narrative(metric_snapshots)
        anomaly_commentary = self._build_anomaly_commentary(anomalies)
        recommended_actions = self._build_default_actions(metric_snapshots, anomalies)

        fallback = NarrativeSections(
            summary=summary,
            trend_narrative=trend_narrative,
            anomaly_commentary=anomaly_commentary,
            recommended_actions=recommended_actions,
        )

        # Build context dict with prompt engineering
        context = {
            "metric_snapshots": [snapshot.model_dump() for snapshot in metric_snapshots],
            "anomalies": [anomaly.model_dump() for anomaly in anomalies],
            "chart_explanation": chart_explanation.model_dump(),
            "report_metadata": {
                "report_title": report_title,
                "records_analyzed": resolved_records,
                "periods_analyzed": resolved_periods,
                "date_range_start": date_range_start,
                "date_range_end": date_range_end,
                "persona": persona.value,
            },
        }

        # Phase 5: Assemble structured prompts
        assembler = PromptAssembler(persona=persona)
        assembly = assembler.assemble(
            anomalies=anomalies,
            metric_snapshots=metric_snapshots,
            report_title=report_title,
            records_analyzed=resolved_records,
            periods_analyzed=resolved_periods,
            chart_base64=chart_base64,
            chart_explanation=chart_explanation,
            chart_mime_type=chart_mime_type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
        )
        context["prompt_context"] = assembly.context_sections

        # Call LLM with structured prompt
        return self.llm_client.generate_sections(
            report_title=report_title,
            context=context,
            fallback=fallback,
            prompt=StructuredPrompt(
                system_prompt=assembly.system_prompt,
                user_prompt=assembly.user_prompt,
            ),
            system_prompt=assembly.system_prompt,
        )

    @staticmethod
    def _build_summary_line(up_trends: list[str], down_trends: list[str]) -> str:
        clauses: list[str] = []
        if up_trends:
            clauses.append(f"Positive momentum is visible in {', '.join(up_trends[:3])}.")
        if down_trends:
            clauses.append(f"Pressure is emerging in {', '.join(down_trends[:3])}.")
        if not clauses:
            return "Trend movement is broadly stable across the tracked metrics."
        return " ".join(clauses)

    @staticmethod
    def _build_trend_narrative(metric_snapshots: list[MetricSnapshot]) -> list[str]:
        narrative: list[str] = []
        for snapshot in metric_snapshots[:5]:
            if snapshot.percent_change is None:
                sentence = (
                    f"{snapshot.metric} closed at {snapshot.latest_value:,.2f} with insufficient history "
                    "for a month-over-month comparison."
                )
            else:
                sentence = (
                    f"{snapshot.metric} closed at {snapshot.latest_value:,.2f}, "
                    f"moving {snapshot.percent_change * 100:.1f}% versus the previous period and "
                    f"maintaining a {snapshot.trend_direction} trend."
                )
            narrative.append(sentence)
        return narrative

    @staticmethod
    def _build_anomaly_commentary(anomalies: list[AnomalyInsight]) -> list[str]:
        if not anomalies:
            return ["No major anomalies crossed the configured thresholds in the latest reporting window."]

        return [
            (
                f"{anomaly.metric} is flagged as {anomaly.severity} severity. "
                f"Latest value {anomaly.latest_value:,.2f}; baseline {anomaly.baseline_value:,.2f}. "
                f"{anomaly.reason}"
            )
            for anomaly in anomalies
        ]

    @staticmethod
    def _build_default_actions(
        metric_snapshots: list[MetricSnapshot],
        anomalies: list[AnomalyInsight],
    ) -> list[str]:
        actions: list[str] = []

        if anomalies:
            actions.append("Investigate the drivers behind the flagged anomalies before the next reporting cycle.")

        for snapshot in metric_snapshots:
            metric = snapshot.metric.lower()
            if snapshot.trend_direction == "down" and ("revenue" in metric or "sales" in metric):
                actions.append("Review pipeline coverage, deal slippage, and win-rate drivers for revenue recovery.")
            if snapshot.trend_direction == "up" and ("expense" in metric or "cost" in metric):
                actions.append("Validate whether the rise in operating costs is intentional and tied to growth priorities.")
            if "churn" in metric and snapshot.latest_value > snapshot.mean_value:
                actions.append("Launch a churn root-cause review across at-risk segments and recent support escalations.")
            if "conversion" in metric and snapshot.trend_direction == "down":
                actions.append("Inspect funnel drop-off points and recent campaign mix shifts impacting conversion.")

        if not actions:
            actions.append("Maintain the current operating plan and continue monitoring KPI movement for early signals.")

        deduped_actions: list[str] = []
        for action in actions:
            if action not in deduped_actions:
                deduped_actions.append(action)
        return deduped_actions[:5]

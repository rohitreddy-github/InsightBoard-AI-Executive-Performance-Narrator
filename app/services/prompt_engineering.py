"""
Phase 5: Prompt Engineering Service

Core service for assembling system prompts, context, and managing prompt chains.
Bridges personas, templates, and context formatting for LLM consumption.
"""

from typing import Any, NamedTuple

from app.models.schemas import AnomalyInsight, ChartExplanation, MetricSnapshot
from app.prompts.context_templates import ContextFormatter, build_complete_user_prompt
from app.prompts.system_prompts import (
    PersonaRole,
    build_comprehensive_system_prompt,
    get_focus_instruction,
    get_system_prompt,
)


class AssemblyContext(NamedTuple):
    """Structured context for prompt assembly."""
    system_prompt: str
    user_prompt: str
    persona: PersonaRole
    context_sections: dict[str, str]  # metadata: "...", metrics: "...", anomalies: "...", etc.


class PromptStep(NamedTuple):
    """Single step in a prompt chain."""
    name: str
    system_instruction: str
    user_prompt_template: str  # Can contain {previous_output} placeholder


class SystemPromptBuilder:
    """Builds persona-specific system prompts with instructions and tone."""

    def __init__(self, persona: PersonaRole = PersonaRole.CFO):
        self.persona = persona

    def build_system_prompt(self) -> str:
        """Return the complete system prompt for the assigned persona."""
        return build_comprehensive_system_prompt(self.persona)

    def build_instructions_only(self) -> str:
        """Return just the focus/constraints instructions."""
        return get_focus_instruction(self.persona)

    def build_base_prompt(self) -> str:
        """Return just the base system prompt (without focus instructions)."""
        return get_system_prompt(self.persona)

    @staticmethod
    def get_all_personas() -> list[PersonaRole]:
        """Return all available personas."""
        return list(PersonaRole)

    def with_persona(self, persona: PersonaRole) -> "SystemPromptBuilder":
        """Create a new builder with a different persona."""
        return SystemPromptBuilder(persona=persona)


class PromptContextBuilder:
    """Assembles structured context from analytics data."""

    def __init__(self):
        self.formatter = ContextFormatter()

    def format_metric(self, snapshot: MetricSnapshot) -> str:
        """Format a single metric."""
        return self.formatter.format_metric_snapshot(snapshot)

    def format_anomaly(self, anomaly: AnomalyInsight) -> str:
        """Format a single anomaly."""
        return self.formatter.format_anomaly_insight(anomaly)

    def build_context_sections(
        self,
        anomalies: list[AnomalyInsight],
        metric_snapshots: list[MetricSnapshot],
        report_title: str,
        records_analyzed: int,
        periods_analyzed: int,
        chart_base64: str | None = None,
        chart_explanation: ChartExplanation | None = None,
        date_range_start: str = "Unknown",
        date_range_end: str = "Unknown",
    ) -> dict[str, str]:
        """Build individual context sections."""
        return {
            "metadata": self.formatter.format_metadata(
                report_title=report_title,
                records_analyzed=records_analyzed,
                periods_analyzed=periods_analyzed,
                date_range_start=date_range_start,
                date_range_end=date_range_end,
            ),
            "metrics": self.formatter.format_statistical_summary(metric_snapshots),
            "anomalies": self.formatter.format_anomalies_section(anomalies),
            "chart": self.formatter.format_chart_context(chart_base64, chart_explanation),
        }

    def build_user_prompt(
        self,
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
        """Build complete user prompt with all context."""
        return build_complete_user_prompt(
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


class PromptAssembler:
    """Assembles system and user prompts for a given persona and context."""

    def __init__(self, persona: PersonaRole = PersonaRole.CFO):
        self.system_builder = SystemPromptBuilder(persona)
        self.context_builder = PromptContextBuilder()
        self.persona = persona

    def assemble(
        self,
        anomalies: list[AnomalyInsight],
        metric_snapshots: list[MetricSnapshot],
        report_title: str,
        records_analyzed: int,
        periods_analyzed: int,
        chart_base64: str | None = None,
        chart_explanation: ChartExplanation | None = None,
        date_range_start: str = "Unknown",
        date_range_end: str = "Unknown",
    ) -> AssemblyContext:
        """Assemble complete prompt context for LLM consumption."""

        system_prompt = self.system_builder.build_system_prompt()
        user_prompt = self.context_builder.build_user_prompt(
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

        context_sections = self.context_builder.build_context_sections(
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

        return AssemblyContext(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            persona=self.persona,
            context_sections=context_sections,
        )

    def with_persona(self, persona: PersonaRole) -> "PromptAssembler":
        """Create a new assembler with a different persona."""
        return PromptAssembler(persona=persona)


class PromptChainExecutor:
    """Executes a sequence of prompts, passing outputs as context to next step."""

    def __init__(self, default_persona: PersonaRole = PersonaRole.CFO):
        self.default_persona = default_persona
        self.step_results: dict[str, dict[str, Any]] = {}

    def execute_chain(
        self,
        steps: list[PromptStep],
        initial_context: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """
        Execute a chain of prompts sequentially.

        Args:
            steps: List of PromptStep objects defining the chain
            initial_context: Initial context dict for the chain

        Returns:
            Dictionary mapping step names to outputs
        """
        self.step_results = {}
        context = initial_context.copy()

        for step in steps:
            # Replace template placeholders with the initial context and previous outputs.
            user_prompt = step.user_prompt_template
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                user_prompt = user_prompt.replace(placeholder, str(value))

            for key, value in self.step_results.items():
                placeholder = f"{{previous_{key}}}"
                replacement = value["user"] if isinstance(value, dict) and "user" in value else str(value)
                user_prompt = user_prompt.replace(placeholder, replacement)

            # In a real implementation, this would call the LLM
            # For now, we just store the prompt for validation
            self.step_results[step.name] = {
                "system": step.system_instruction,
                "user": user_prompt,
                "context": context,
            }
            context[f"previous_{step.name}"] = user_prompt

        return self.step_results

    def get_step_result(self, step_name: str) -> dict[str, Any] | None:
        """Retrieve the result of a specific step."""
        return self.step_results.get(step_name)


# ============================================================================
# Convenience Functions
# ============================================================================

def build_prompt_for_persona(
    persona: PersonaRole,
    anomalies: list[AnomalyInsight],
    metric_snapshots: list[MetricSnapshot],
    report_title: str,
    records_analyzed: int,
    periods_analyzed: int,
    chart_base64: str | None = None,
    chart_explanation: ChartExplanation | None = None,
    date_range_start: str = "Unknown",
    date_range_end: str = "Unknown",
) -> AssemblyContext:
    """
    One-function convenience to build complete prompt for a persona.

    Quick way to assemble (system_prompt, user_prompt) for LLM consumption.
    """
    assembler = PromptAssembler(persona=persona)
    return assembler.assemble(
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


def get_available_personas() -> list[str]:
    """Get list of available personas by name."""
    return [p.value for p in PersonaRole]

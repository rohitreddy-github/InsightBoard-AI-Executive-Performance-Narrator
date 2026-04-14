from typing import Any, Protocol
from typing_extensions import NamedTuple

from app.models.schemas import NarrativeSections


class StructuredPrompt(NamedTuple):
    """Structured prompt with system and user components."""
    system_prompt: str
    user_prompt: str


class LLMClient(Protocol):
    def generate_sections(
        self,
        report_title: str,
        context: dict[str, Any],
        fallback: NarrativeSections,
        prompt: StructuredPrompt | None = None,
        system_prompt: str | None = None,
    ) -> NarrativeSections:
        """
        Generate narrative sections from context.

        Args:
            report_title: Title of the report
            context: Context dict with structured data
            fallback: Fallback narrative if LLM fails
            prompt: Optional structured prompt bundle with system and user prompts
            system_prompt: Optional persona-specific system prompt

        Returns:
            NarrativeSections with generated narrative
        """
        ...


class MockLLMClient:
    """Mock LLM client that returns fallback narratives."""

    def generate_sections(
        self,
        report_title: str,
        context: dict[str, Any],
        fallback: NarrativeSections,
        prompt: StructuredPrompt | None = None,
        system_prompt: str | None = None,
    ) -> NarrativeSections:
        """Mock implementation always returns fallback."""
        return fallback

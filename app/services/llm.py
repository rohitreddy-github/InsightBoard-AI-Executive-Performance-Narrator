from typing import Any, Protocol

from app.models.schemas import NarrativeSections


class LLMClient(Protocol):
    def generate_sections(
        self,
        report_title: str,
        context: dict[str, Any],
        fallback: NarrativeSections,
    ) -> NarrativeSections:
        ...


class MockLLMClient:
    def generate_sections(
        self,
        report_title: str,
        context: dict[str, Any],
        fallback: NarrativeSections,
    ) -> NarrativeSections:
        return fallback

import base64
import json
import re
from typing import Any, Protocol

from pydantic import ValidationError
from typing_extensions import NamedTuple

from app.models.schemas import LLMNarrativeResponse, NarrativeSections


JSON_RESPONSE_INSTRUCTION = """
Return only valid JSON with this exact shape:
{
  "executive_summary": "string",
  "trend_analysis": ["string"],
  "anomaly_explanation": ["string"],
  "action_items": ["string"]
}

Do not wrap the JSON in markdown fences.
""".strip()


class StructuredPrompt(NamedTuple):
    """Structured prompt with system and user components."""
    system_prompt: str
    user_prompt: str


class MultimodalPromptPayload(NamedTuple):
    """Normalized multimodal prompt bundle for provider adapters."""
    system_prompt: str
    user_text: str
    image_data_uri: str | None
    image_bytes: bytes | None
    image_mime_type: str | None


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


class OpenAIResponsesLLMClient:
    """OpenAI Responses API adapter with multimodal chart support."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 60.0,
        image_detail: str = "high",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.image_detail = image_detail

    def generate_sections(
        self,
        report_title: str,
        context: dict[str, Any],
        fallback: NarrativeSections,
        prompt: StructuredPrompt | None = None,
        system_prompt: str | None = None,
    ) -> NarrativeSections:
        if not self.api_key or prompt is None:
            return fallback

        try:
            from openai import OpenAI
        except ImportError:
            return fallback

        payload = build_multimodal_payload(prompt=prompt, context=context, system_prompt=system_prompt)
        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)

        user_content: list[dict[str, Any]] = [{"type": "input_text", "text": payload.user_text}]
        if payload.image_data_uri is not None:
            user_content.append(
                {
                    "type": "input_image",
                    "image_url": payload.image_data_uri,
                    "detail": self.image_detail,
                }
            )

        try:
            response = client.responses.create(
                model=self.model,
                instructions=payload.system_prompt,
                input=[{"role": "user", "content": user_content}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "executive_narrative",
                        "strict": True,
                        "schema": get_llm_narrative_json_schema(),
                    }
                },
            )
        except Exception:
            return fallback

        response_text = getattr(response, "output_text", "") or extract_openai_output_text(response)
        return parse_narrative_sections(response_text, fallback)


class GeminiLLMClient:
    """Gemini SDK adapter with text-plus-image chart input."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 60.0,
        temperature: float = 0.2,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def generate_sections(
        self,
        report_title: str,
        context: dict[str, Any],
        fallback: NarrativeSections,
        prompt: StructuredPrompt | None = None,
        system_prompt: str | None = None,
    ) -> NarrativeSections:
        if not self.api_key or prompt is None:
            return fallback

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            return fallback

        payload = build_multimodal_payload(prompt=prompt, context=context, system_prompt=system_prompt)
        client = genai.Client(api_key=self.api_key)
        contents: list[Any] = [payload.user_text]
        if payload.image_bytes is not None and payload.image_mime_type is not None:
            contents.append(
                types.Part.from_bytes(
                    data=payload.image_bytes,
                    mime_type=payload.image_mime_type,
                )
            )

        try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=payload.system_prompt,
                        temperature=self.temperature,
                        response_mime_type="application/json",
                        response_json_schema=get_llm_narrative_json_schema(),
                        http_options={"timeout": self.timeout_seconds},
                    ),
                )
        except TypeError:
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=payload.system_prompt,
                        temperature=self.temperature,
                        response_mime_type="application/json",
                        response_json_schema=get_llm_narrative_json_schema(),
                    ),
                )
            except Exception:
                return fallback
        except Exception:
            return fallback

        response_text = getattr(response, "text", "") or extract_gemini_output_text(response)
        return parse_narrative_sections(response_text, fallback)


def build_multimodal_payload(
    prompt: StructuredPrompt | None,
    context: dict[str, Any],
    system_prompt: str | None = None,
) -> MultimodalPromptPayload:
    """Combine structured prompts and embedded chart context into provider-ready inputs."""
    resolved_prompt = prompt or StructuredPrompt(
        system_prompt=system_prompt or "",
        user_prompt=json.dumps(context, default=str),
    )
    image_mime_type, image_base64 = extract_chart_payload(context)
    image_data_uri = None
    image_bytes = None
    if image_base64 is not None and image_mime_type is not None:
        image_data_uri = f"data:{image_mime_type};base64,{image_base64}"
        image_bytes = base64.b64decode(image_base64)

    return MultimodalPromptPayload(
        system_prompt=(system_prompt or resolved_prompt.system_prompt).strip(),
        user_text=build_json_output_prompt(resolved_prompt.user_prompt),
        image_data_uri=image_data_uri,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
    )


def build_openai_input_content(payload: MultimodalPromptPayload, image_detail: str = "high") -> list[dict[str, Any]]:
    """Build OpenAI Responses API content parts."""
    content: list[dict[str, Any]] = [{"type": "input_text", "text": payload.user_text}]
    if payload.image_data_uri is not None:
        content.append(
            {
                "type": "input_image",
                "image_url": payload.image_data_uri,
                "detail": image_detail,
            }
        )
    return content


def build_gemini_contents(payload: MultimodalPromptPayload) -> list[dict[str, Any]]:
    """Build Gemini content parts in a serializable test-friendly shape."""
    contents: list[dict[str, Any]] = [{"type": "text", "text": payload.user_text}]
    if payload.image_bytes is not None and payload.image_mime_type is not None:
        contents.append(
            {
                "type": "inline_data",
                "mime_type": payload.image_mime_type,
                "data_base64": base64.b64encode(payload.image_bytes).decode("utf-8"),
            }
        )
    return contents


def build_json_output_prompt(user_prompt: str) -> str:
    """Append a stable JSON response contract to the analytical prompt."""
    return f"{user_prompt}\n\n{JSON_RESPONSE_INSTRUCTION}"


def get_llm_narrative_json_schema() -> dict[str, Any]:
    """Provider-safe JSON schema for narrative synthesis output."""
    return LLMNarrativeResponse.model_json_schema()


def extract_chart_payload(context: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract chart mime type and Base64 data from prompt context XML."""
    prompt_context = context.get("prompt_context", {})
    chart_context = prompt_context.get("chart", "")
    if not chart_context:
        return None, None

    mime_match = re.search(r'mime_type="([^"]+)"', chart_context)
    image_match = re.search(
        r"<chart_image_base64>\s*(.*?)\s*</chart_image_base64>",
        chart_context,
        re.DOTALL,
    )
    if image_match is None:
        return None, None

    mime_type = mime_match.group(1) if mime_match is not None else "image/png"
    image_base64 = re.sub(r"\s+", "", image_match.group(1))
    return mime_type, image_base64


def parse_narrative_sections(response_text: str, fallback: NarrativeSections) -> NarrativeSections:
    """Parse model JSON safely, falling back if the output is unusable."""
    cleaned = response_text.strip()
    if not cleaned:
        return fallback

    try:
        return LLMNarrativeResponse.model_validate_json(cleaned).to_narrative_sections()
    except ValidationError:
        return fallback


def extract_openai_output_text(response: Any) -> str:
    """Best-effort extraction for OpenAI SDK response objects."""
    output = getattr(response, "output", None)
    if not output:
        return ""

    text_fragments: list[str] = []
    for item in output:
        content = getattr(item, "content", None)
        if content is None and isinstance(item, dict):
            content = item.get("content", [])
        for part in content or []:
            part_type = getattr(part, "type", None)
            if part_type is None and isinstance(part, dict):
                part_type = part.get("type")
            if part_type == "output_text":
                text_value = getattr(part, "text", None)
                if text_value is None and isinstance(part, dict):
                    text_value = part.get("text")
                if text_value:
                    text_fragments.append(str(text_value))
    return "\n".join(text_fragments)


def extract_gemini_output_text(response: Any) -> str:
    """Best-effort extraction for Gemini SDK response objects."""
    candidates = getattr(response, "candidates", None)
    if not candidates:
        return ""

    text_fragments: list[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None and isinstance(candidate, dict):
            content = candidate.get("content")
        parts = getattr(content, "parts", None) if content is not None else None
        if parts is None and isinstance(content, dict):
            parts = content.get("parts", [])
        for part in parts or []:
            text_value = getattr(part, "text", None)
            if text_value is None and isinstance(part, dict):
                text_value = part.get("text")
            if text_value:
                text_fragments.append(str(text_value))
    return "\n".join(text_fragments)


def build_llm_client(settings: Any) -> LLMClient:
    """Construct the configured LLM client from application settings."""
    provider = str(getattr(settings, "default_llm_provider", "mock")).lower()

    if provider == "openai":
        return OpenAIResponsesLLMClient(
            api_key=getattr(settings, "openai_api_key", None),
            model=getattr(settings, "openai_model", None) or getattr(settings, "default_llm_model", "gpt-4.1-mini"),
            timeout_seconds=getattr(settings, "llm_timeout_seconds", 60.0),
            image_detail=getattr(settings, "openai_vision_detail", "high"),
        )
    if provider == "gemini":
        return GeminiLLMClient(
            api_key=getattr(settings, "gemini_api_key", None),
            model=getattr(settings, "gemini_model", None) or getattr(settings, "default_llm_model", "gemini-2.5-flash"),
            timeout_seconds=getattr(settings, "llm_timeout_seconds", 60.0),
            temperature=getattr(settings, "llm_temperature", 0.2),
        )
    return MockLLMClient()

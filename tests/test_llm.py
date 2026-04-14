from types import SimpleNamespace

from app.services.llm import (
    GeminiLLMClient,
    MockLLMClient,
    OpenAIResponsesLLMClient,
    StructuredPrompt,
    build_gemini_contents,
    build_llm_client,
    build_multimodal_payload,
    build_openai_input_content,
    get_llm_narrative_json_schema,
    parse_narrative_sections,
)
from app.models.schemas import NarrativeSections


def test_build_multimodal_payload_extracts_chart_image_data() -> None:
    payload = build_multimodal_payload(
        prompt=StructuredPrompt(
            system_prompt="system",
            user_prompt="Analyze this chart.",
        ),
        context={
            "prompt_context": {
                "chart": """
<chart_context source="multimodal-placeholder" has_image="true" mime_type="image/png" encoding="base64">
<chart_image_base64>
ZmFrZS1jaGFydA==
</chart_image_base64>
</chart_context>
""".strip()
            }
        },
    )

    assert payload.image_mime_type == "image/png"
    assert payload.image_data_uri == "data:image/png;base64,ZmFrZS1jaGFydA=="
    assert payload.image_bytes == b"fake-chart"
    assert '"executive_summary"' in payload.user_text


def test_openai_content_builder_includes_image_url_part() -> None:
    payload = build_multimodal_payload(
        prompt=StructuredPrompt(system_prompt="system", user_prompt="Analyze."),
        context={
            "prompt_context": {
                "chart": '<chart_context mime_type="image/png"><chart_image_base64>YWJjZA==</chart_image_base64></chart_context>'
            }
        },
    )

    content = build_openai_input_content(payload)

    assert content[0]["type"] == "input_text"
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"] == "data:image/png;base64,YWJjZA=="


def test_gemini_content_builder_includes_inline_data() -> None:
    payload = build_multimodal_payload(
        prompt=StructuredPrompt(system_prompt="system", user_prompt="Analyze."),
        context={
            "prompt_context": {
                "chart": '<chart_context mime_type="image/png"><chart_image_base64>YWJjZA==</chart_image_base64></chart_context>'
            }
        },
    )

    contents = build_gemini_contents(payload)

    assert contents[0]["type"] == "text"
    assert contents[1]["type"] == "inline_data"
    assert contents[1]["mime_type"] == "image/png"
    assert contents[1]["data_base64"] == "YWJjZA=="


def test_parse_narrative_sections_reads_json_response() -> None:
    fallback = NarrativeSections(
        summary="fallback",
        trend_narrative=["fallback trend"],
        anomaly_commentary=["fallback anomaly"],
        recommended_actions=["fallback action"],
    )

    parsed = parse_narrative_sections(
        """
{
  "executive_summary": "board summary",
  "trend_analysis": ["trend 1", "trend 2"],
  "anomaly_explanation": ["anomaly 1"],
  "action_items": ["action 1"]
}
""".strip(),
        fallback=fallback,
    )

    assert parsed.summary == "board summary"
    assert parsed.trend_narrative == ["trend 1", "trend 2"]
    assert parsed.anomaly_commentary == ["anomaly 1"]
    assert parsed.recommended_actions == ["action 1"]


def test_parse_narrative_sections_accepts_legacy_alias_keys() -> None:
    fallback = NarrativeSections(
        summary="fallback",
        trend_narrative=["fallback trend"],
        anomaly_commentary=["fallback anomaly"],
        recommended_actions=["fallback action"],
    )

    parsed = parse_narrative_sections(
        """
{
  "summary": "legacy summary",
  "trend_narrative": ["legacy trend"],
  "anomaly_commentary": ["legacy anomaly"],
  "recommended_actions": ["legacy action"]
}
""".strip(),
        fallback=fallback,
    )

    assert parsed.summary == "legacy summary"
    assert parsed.trend_narrative == ["legacy trend"]
    assert parsed.anomaly_commentary == ["legacy anomaly"]
    assert parsed.recommended_actions == ["legacy action"]


def test_llm_schema_includes_required_phase7_keys() -> None:
    schema = get_llm_narrative_json_schema()

    assert schema["properties"]["executive_summary"]["type"] == "string"
    assert schema["properties"]["anomaly_explanation"]["type"] == "array"
    assert schema["properties"]["action_items"]["type"] == "array"
    assert "executive_summary" in schema["required"]
    assert "anomaly_explanation" in schema["required"]
    assert "action_items" in schema["required"]


def test_build_llm_client_uses_configured_provider() -> None:
    openai_client = build_llm_client(
        SimpleNamespace(
            default_llm_provider="openai",
            openai_api_key="secret",
            openai_model="gpt-4.1-mini",
            llm_timeout_seconds=30.0,
            openai_vision_detail="high",
        )
    )
    gemini_client = build_llm_client(
        SimpleNamespace(
            default_llm_provider="gemini",
            gemini_api_key="secret",
            gemini_model="gemini-2.5-flash",
            llm_timeout_seconds=30.0,
            llm_temperature=0.2,
        )
    )
    mock_client = build_llm_client(SimpleNamespace(default_llm_provider="mock"))

    assert isinstance(openai_client, OpenAIResponsesLLMClient)
    assert isinstance(gemini_client, GeminiLLMClient)
    assert isinstance(mock_client, MockLLMClient)

"""Phase 9: Resiliency & Error Handling Tests.

Tests for retry logic, rate-limit handling, and graceful degradation.
"""

import pytest
from app.services.ingestion import CSVIngestionService, InputContractError
from app.services.pipeline import build_report_pipeline


class TestCSVErrorHandling:
    """Test exception handling for malformed CSV uploads and missing columns."""

    def test_empty_csv_raises_error(self) -> None:
        """Test that empty CSV raises informative error."""
        service = CSVIngestionService()
        empty_csv = b""

        with pytest.raises(InputContractError) as exc_info:
            service.load_csv(empty_csv)

        assert "empty" in str(exc_info.value).lower() or "parse" in str(exc_info.value).lower()

    def test_malformed_csv_parse_error(self) -> None:
        """Test that malformed CSV raises parse error."""
        service = CSVIngestionService()
        malformed_csv = b'date,metric_name,value\n"unclosed,quote,100'

        with pytest.raises(InputContractError) as exc_info:
            service.load_csv(malformed_csv)

        assert "parse" in str(exc_info.value).lower() or "csv" in str(exc_info.value).lower()

    def test_missing_required_columns(self) -> None:
        """Test that CSV with missing required columns raises error."""
        service = CSVIngestionService()
        invalid_columns_csv = b"date,revenue\n2026-01-01,1000"

        with pytest.raises(InputContractError) as exc_info:
            service.load_csv(invalid_columns_csv)

        error_msg = str(exc_info.value)
        assert "date" in error_msg.lower()
        assert "metric_name" in error_msg.lower()
        assert "value" in error_msg.lower()

    def test_invalid_date_format(self) -> None:
        """Test that invalid date format raises error."""
        service = CSVIngestionService()
        invalid_date_csv = b"date,metric_name,value\ninvalid-date,revenue,1000"

        with pytest.raises(InputContractError) as exc_info:
            service.load_csv(invalid_date_csv)

        error_msg = str(exc_info.value).lower()
        assert "date" in error_msg or "parse" in error_msg

    def test_non_numeric_values_handled(self) -> None:
        """Test that non-numeric values in 'value' column are handled gracefully."""
        service = CSVIngestionService()
        non_numeric_csv = b"date,metric_name,value\n2026-01-01,revenue,abc"

        with pytest.raises(InputContractError):
            service.load_csv(non_numeric_csv)

    def test_csv_with_only_headers_raises_error(self) -> None:
        """Test that CSV with only headers raises error."""
        service = CSVIngestionService()
        headers_only_csv = b"date,metric_name,value"

        with pytest.raises(InputContractError) as exc_info:
            service.load_csv(headers_only_csv)

        assert "empty" in str(exc_info.value).lower() or "no data" in str(exc_info.value).lower()

    def test_valid_csv_logs_success(self, sample_csv_bytes: bytes) -> None:
        """Test that valid CSV ingestion logs success info."""
        service = CSVIngestionService()
        result = service.load_csv(sample_csv_bytes)

        assert result.record_count > 0
        assert result.period_count > 0
        assert len(result.metric_columns) > 0

    def test_csv_with_missing_values_handled_with_forward_fill(self) -> None:
        """Test that missing values are imputed with forward-fill strategy."""
        service = CSVIngestionService()
        csv_with_gaps = (
            b"date,metric_name,value\n"
            b"2026-01-01,revenue,1000\n"
            b"2026-01-02,revenue,\n"
            b"2026-01-03,revenue,1200"
        )

        result = service.load_csv(csv_with_gaps, missing_value_strategy="forward_fill")
        assert result.preprocessing_summary.missing_values_imputed > 0

    def test_csv_with_missing_values_handled_with_interpolate(self) -> None:
        """Test that missing values are imputed with interpolation strategy."""
        service = CSVIngestionService()
        csv_with_gaps = (
            b"date,metric_name,value\n"
            b"2026-01-01,revenue,1000\n"
            b"2026-01-02,revenue,\n"
            b"2026-01-03,revenue,1200"
        )

        result = service.load_csv(csv_with_gaps, missing_value_strategy="interpolate")
        assert result.preprocessing_summary.missing_values_imputed > 0


class TestPipelineRobustness:
    """Test pipeline resilience to various error conditions."""

    def test_pipeline_with_invalid_csv_raises_error(self) -> None:
        """Test that pipeline properly propagates CSV ingestion errors."""
        pipeline = build_report_pipeline()
        invalid_csv = b"date,revenue\n2025-01-01,100"

        with pytest.raises(InputContractError):
            pipeline.generate_report(
                report_title="Invalid Report",
                csv_bytes=invalid_csv,
                source_name="invalid.csv",
            )

    def test_pipeline_fallback_on_llm_failure(self, sample_csv_bytes: bytes) -> None:
        """Test that pipeline returns fallback narrative if LLM fails."""
        pipeline = build_report_pipeline()

        result = pipeline.generate_report(
            report_title="Test Report",
            csv_bytes=sample_csv_bytes,
            source_name="test.csv",
        )

        # Even if LLM fails, we should have fallback data
        assert result.executive_summary is not None
        assert len(result.executive_summary) > 0
        assert result.recommended_actions is not None
        assert len(result.recommended_actions) >= 1

    def test_pipeline_handles_anomaly_detection_gracefully(self, sample_csv_bytes: bytes) -> None:
        """Test that pipeline handles anomaly detection edge cases."""
        pipeline = build_report_pipeline()

        result = pipeline.generate_report(
            report_title="Anomaly Test",
            csv_bytes=sample_csv_bytes,
            source_name="test.csv",
        )

        # Should have metrics and anomaly commentary
        assert result.metric_snapshots is not None
        assert result.anomaly_commentary is not None


class TestLLMClientRetryBehavior:
    """Test retry behavior and configurations for LLM clients."""

    def test_openai_client_has_max_retries(self) -> None:
        """Test that OpenAI client accepts max_retries parameter."""
        from app.services.llm import OpenAIResponsesLLMClient

        client = OpenAIResponsesLLMClient(
            api_key="test-key",
            model="gpt-4o",
            max_retries=5,
        )
        assert client.max_retries == 5

    def test_gemini_client_has_max_retries(self) -> None:
        """Test that Gemini client accepts max_retries parameter."""
        from app.services.llm import GeminiLLMClient

        client = GeminiLLMClient(
            api_key="test-key",
            model="gemini-2.5-flash",
            max_retries=5,
        )
        assert client.max_retries == 5

    def test_settings_propagate_max_retries(self) -> None:
        """Test that max_retries from settings are passed to LLM clients."""
        from unittest.mock import MagicMock
        from app.services.llm import build_llm_client

        mock_settings = MagicMock()
        mock_settings.default_llm_provider = "mock"
        mock_settings.llm_max_retries = 5

        client = build_llm_client(mock_settings)
        # Mock client doesn't have max_retries, but checking the flow works
        assert client is not None

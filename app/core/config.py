from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.schemas import MissingValueStrategy, TimeAggregation


class Settings(BaseSettings):
    app_name: str = "InsightBoard AI Executive Performance Narrator"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    default_llm_provider: str = "mock"
    default_llm_model: str = "executive-summary-model"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_retries: int = Field(default=3, ge=1, le=10)
    openai_vision_detail: str = "high"
    anomaly_zscore_threshold: float = Field(default=2.0, gt=0)
    latest_change_alert_threshold: float = Field(default=0.15, gt=0)
    default_aggregation_granularity: TimeAggregation = "monthly"
    default_missing_value_strategy: MissingValueStrategy = "forward_fill"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="INSIGHTBOARD_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

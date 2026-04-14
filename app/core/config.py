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

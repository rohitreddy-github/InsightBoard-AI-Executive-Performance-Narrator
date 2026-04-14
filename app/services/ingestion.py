from dataclasses import dataclass
from io import BytesIO

import pandas as pd
from pydantic import TypeAdapter, ValidationError

from app.models.schemas import (
    CSVColumnContract,
    InputDataContract,
    KPIRecordInput,
    MissingValueStrategy,
    PreprocessingSummary,
    TimeAggregation,
)


@dataclass(slots=True)
class DatasetBundle:
    frame: pd.DataFrame
    raw_frame: pd.DataFrame
    date_column: str
    metric_columns: list[str]
    dimension_columns: list[str]
    record_count: int
    period_count: int
    preprocessing_summary: PreprocessingSummary


class InputContractError(ValueError):
    """Raised when an uploaded CSV does not match the canonical schema."""


class CSVIngestionService:
    REQUIRED_COLUMNS = ("date", "metric_name", "value")
    RECORD_ADAPTER = TypeAdapter(list[KPIRecordInput])
    RATE_METRIC_HINTS = ("rate", "ratio", "margin", "pct", "percent", "nps", "score", "avg")
    LAST_VALUE_METRIC_HINTS = ("headcount", "balance", "cash", "arr", "mrr", "inventory")
    FREQUENCY_ALIASES: dict[TimeAggregation, str] = {
        "weekly": "W-MON",
        "monthly": "MS",
    }

    def load_csv(
        self,
        csv_bytes: bytes,
        aggregation_granularity: TimeAggregation = "monthly",
        missing_value_strategy: MissingValueStrategy = "forward_fill",
    ) -> DatasetBundle:
        raw_frame = pd.read_csv(BytesIO(csv_bytes))
        raw_frame.columns = [self._normalize_column_name(column) for column in raw_frame.columns]
        raw_frame = raw_frame.dropna(how="all").reset_index(drop=True)

        self._validate_columns(raw_frame)
        records = self._validate_records(raw_frame)
        validated_frame = pd.DataFrame(record.model_dump() for record in records)
        validated_frame["date"] = pd.to_datetime(validated_frame["date"], errors="coerce")
        validated_frame["metric_name"] = validated_frame["metric_name"].map(self._normalize_metric_name)
        validated_frame["value"] = pd.to_numeric(validated_frame["value"], errors="coerce")

        invalid_dates = validated_frame["date"].isna()
        if invalid_dates.any():
            raise InputContractError(
                "CSV contains unparseable date values at rows "
                f"{validated_frame.index[invalid_dates].tolist()}."
            )

        rows_received = len(validated_frame)
        missing_values_detected = int(validated_frame["value"].isna().sum())

        deduped_frame = validated_frame.drop_duplicates(ignore_index=True)
        exact_duplicate_rows_removed = rows_received - len(deduped_frame)
        date_metric_duplicates_collapsed = (
            len(deduped_frame)
            - len(deduped_frame.groupby(["date", "metric_name"], dropna=False))
        )

        processed_long_frame, missing_values_imputed = self._preprocess_time_series(
            deduped_frame,
            aggregation_granularity=aggregation_granularity,
            missing_value_strategy=missing_value_strategy,
        )
        pivot_frame = processed_long_frame.pivot(
            index="date",
            columns="metric_name",
            values="value",
        ).sort_index()

        if pivot_frame.empty:
            raise InputContractError("CSV preprocessing produced no usable KPI observations.")

        pivot_frame = pivot_frame.reset_index()
        metric_columns = [column for column in pivot_frame.columns if column != "date"]
        if not metric_columns:
            raise InputContractError("CSV must contain at least one metric_name/value observation.")

        preprocessing_summary = PreprocessingSummary(
            aggregation_granularity=aggregation_granularity,
            missing_value_strategy=missing_value_strategy,
            rows_received=rows_received,
            exact_duplicate_rows_removed=exact_duplicate_rows_removed,
            date_metric_duplicates_collapsed=date_metric_duplicates_collapsed,
            missing_values_detected=missing_values_detected,
            missing_values_imputed=missing_values_imputed,
            output_periods_generated=int(pivot_frame["date"].nunique()),
        )

        return DatasetBundle(
            frame=pivot_frame,
            raw_frame=validated_frame,
            date_column="date",
            metric_columns=metric_columns,
            dimension_columns=[],
            record_count=rows_received,
            period_count=pivot_frame["date"].nunique(),
            preprocessing_summary=preprocessing_summary,
        )

    def get_input_contract(self) -> InputDataContract:
        return InputDataContract(
            format="long",
            description=(
                "Canonical KPI ingestion schema for KPI time-series reporting. Each CSV row "
                "represents one metric observation for one reporting date before preprocessing."
            ),
            required_columns=[
                CSVColumnContract(
                    name="date",
                    data_type="date-like string",
                    required=True,
                    description="Reporting date for the KPI observation, for example 2026-03-01 or 03/01/2026.",
                ),
                CSVColumnContract(
                    name="metric_name",
                    data_type="string",
                    required=True,
                    description="Business KPI name, such as revenue, churn_rate, or nps.",
                ),
                CSVColumnContract(
                    name="value",
                    data_type="float",
                    required=True,
                    description="Numeric KPI observation on the given date; blank values may be imputed during preprocessing.",
                ),
            ],
            allowed_columns=list(self.REQUIRED_COLUMNS),
            example_row=KPIRecordInput(
                date="2026-03-01",
                metric_name="revenue",
                value=520000.0,
            ),
            validation_rules=[
                "CSV headers must be exactly: date, metric_name, value.",
                "Each row must map cleanly to the KPIRecordInput schema.",
                "date values must parse into valid datetimes via pandas preprocessing.",
                "value must be numeric when present; blanks are allowed and handled by the missing value strategy.",
                "Exact duplicate rows are removed before preprocessing.",
                "Multiple rows for the same date + metric_name are aggregated during preprocessing.",
                "Data is standardized to daily continuity before weekly or monthly bucketing.",
            ],
        )

    def _validate_columns(self, frame: pd.DataFrame) -> None:
        actual_columns = list(frame.columns)
        expected_columns = list(self.REQUIRED_COLUMNS)
        if actual_columns != expected_columns:
            raise InputContractError(
                f"CSV columns must exactly match {expected_columns}. Received {actual_columns}."
            )

    def _validate_records(self, frame: pd.DataFrame) -> list[KPIRecordInput]:
        raw_records = frame.where(pd.notna(frame), None).to_dict(orient="records")
        try:
            return self.RECORD_ADAPTER.validate_python(raw_records)
        except ValidationError as exc:
            raise InputContractError(f"CSV row validation failed: {exc}") from exc

    def _preprocess_time_series(
        self,
        frame: pd.DataFrame,
        aggregation_granularity: TimeAggregation,
        missing_value_strategy: MissingValueStrategy,
    ) -> tuple[pd.DataFrame, int]:
        frequency = self.FREQUENCY_ALIASES[aggregation_granularity]
        processed_frames: list[pd.DataFrame] = []
        missing_values_imputed = 0

        for metric_name, metric_frame in frame.groupby("metric_name", sort=True):
            metric_daily = (
                metric_frame.groupby("date", sort=True)["value"]
                .apply(lambda series: self._aggregate_metric_values(metric_name, series))
                .sort_index()
            )
            if metric_daily.empty:
                continue

            full_daily_index = pd.date_range(
                metric_daily.index.min(),
                metric_daily.index.max(),
                freq="D",
            )
            metric_daily = metric_daily.reindex(full_daily_index)
            missing_before = int(metric_daily.isna().sum())
            metric_daily = self._apply_missing_value_strategy(metric_daily, missing_value_strategy)
            missing_after = int(metric_daily.isna().sum())
            missing_values_imputed += max(0, missing_before - missing_after)

            bucketed = metric_daily.resample(frequency).apply(
                lambda series: self._aggregate_metric_values(metric_name, series)
            )
            bucketed = bucketed.dropna()
            if bucketed.empty:
                continue

            processed_frames.append(
                pd.DataFrame(
                    {
                        "date": bucketed.index,
                        "metric_name": metric_name,
                        "value": bucketed.values,
                    }
                )
            )

        if not processed_frames:
            raise InputContractError("CSV preprocessing produced no usable KPI observations.")

        processed_long_frame = pd.concat(processed_frames, ignore_index=True)
        return processed_long_frame, missing_values_imputed

    def _aggregate_metric_values(self, metric_name: str, series: pd.Series) -> float | None:
        non_null_series = series.dropna()
        if non_null_series.empty:
            return None

        normalized_metric = self._normalize_metric_name(metric_name)
        if any(hint in normalized_metric for hint in self.LAST_VALUE_METRIC_HINTS):
            return float(non_null_series.iloc[-1])
        if any(hint in normalized_metric for hint in self.RATE_METRIC_HINTS):
            return float(non_null_series.mean())
        return float(non_null_series.sum())

    @staticmethod
    def _apply_missing_value_strategy(
        series: pd.Series,
        strategy: MissingValueStrategy,
    ) -> pd.Series:
        if strategy == "drop":
            return series
        if strategy == "forward_fill":
            return series.ffill()
        if strategy == "interpolate":
            return series.interpolate(limit_direction="both")
        return series

    @staticmethod
    def _normalize_column_name(column: str) -> str:
        return column.strip().lower().replace(" ", "_")

    @staticmethod
    def _normalize_metric_name(metric_name: str) -> str:
        return metric_name.strip().lower().replace(" ", "_")

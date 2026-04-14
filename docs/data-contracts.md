# Data Contracts

## Canonical ingestion schema

Phase 1 and Phase 2 standardize CSV ingestion around one long-format contract:

| Column | Type | Required | Description |
| --- | --- | --- | --- |
| `date` | date-like string | Yes | Reporting date for the KPI observation |
| `metric_name` | string | Yes | KPI identifier such as `revenue` or `churn_rate` |
| `value` | float | Yes | Numeric KPI observation for the given date; blanks may be imputed during preprocessing |

## Validation rules

- CSV headers must be exactly `date,metric_name,value`
- each row must validate against the `KPIRecordInput` Pydantic schema
- `date` must parse into a valid datetime during preprocessing
- `value` must be numeric when present
- exact duplicate rows are removed before processing
- multiple rows for the same `date + metric_name` are collapsed during preprocessing
- the series is standardized to daily continuity before weekly or monthly aggregation

## Preprocessing behavior

- `pd.read_csv()` is used for ingestion
- dates are standardized with `pd.to_datetime(...)`
- each metric is expanded to a daily time series between its min and max observed dates
- missing daily values can be handled with `drop`, `forward_fill`, or `interpolate`
- processed daily series are aggregated into `weekly` or `monthly` buckets

## Why this contract exists

- It gives the model layer deterministic inputs.
- It separates ingestion shape from downstream analytical shape.
- It prevents ambiguous wide-format uploads from slipping into prompt assembly.
- It creates a stable base for future dimensions, targets, and benchmarking metadata.

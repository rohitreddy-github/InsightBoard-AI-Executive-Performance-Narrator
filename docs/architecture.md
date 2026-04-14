# Architecture Overview

## Phase 1 goal

Phase 1 establishes strict data contracts and a deterministic workflow before introducing real LLM inference. The canonical ingestion format is a long-form CSV with exactly three columns: `date`, `metric_name`, and `value`.

## Phase 2 goal

Phase 2 adds real preprocessing behavior on top of that contract: date normalization, exact duplicate removal, missing-value handling, and aggregation into weekly or monthly reporting buckets.

## System workflow

1. Ingestion: `CSVIngestionService` reads CSV input with pandas and validates row structure against `KPIRecordInput`.
2. Processing: validated rows are normalized into daily metric series, missing values are handled, and data is aggregated into the requested weekly or monthly buckets before pivoting into a metric matrix.
3. Visualization: chart context is summarized and reserved for future multimodal reasoning.
4. Prompt Assembly: structured KPI signals are organized into deterministic LLM-ready context.
5. LLM Inference: executive narration and recommendations are produced from validated context.
6. Output: the API returns a structured report payload for a UI, export service, or workflow engine.

## Architectural decisions

- Canonical input is long-format rather than wide-format.
- Schema validation happens before any analytical transformation.
- Preprocessing standardizes data to daily continuity before higher-level aggregation.
- Prompt assembly is treated as its own stage to keep LLM inputs auditable.
- Visualization is a first-class stage even before full multimodal support is added.

## Suggested next production steps

- Add a real LLM provider adapter behind `app/services/llm.py`.
- Add persistent report storage and audit logs.
- Add authentication, request tracing, and rate limiting.
- Extend anomaly detection with seasonality-aware methods and peer group baselines.
- Support direct chart parsing via a vision-capable model endpoint.

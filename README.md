# InsightBoard AI Executive Performance Narrator

Production-grade starter repository for turning structured KPI data into executive-ready business narratives.

## Current phase

The project is now through:

- **Phase 1: System Architecture & Data Modeling**
- **Phase 2: Data Ingestion & Preprocessing (Pandas)**

The repository now enforces a canonical long-format CSV contract and preprocesses real-world KPI time series before analytics and narrative generation.

- Canonical CSV shape: `date`, `metric_name`, `value`
- Workflow: `Ingestion -> Processing -> Visualization -> Prompt Assembly -> LLM Inference -> Output`
- Cleaning: datetime normalization, exact duplicate removal, missing-value imputation, weekly/monthly bucketing

## What this project is for

Business analytics teams often spend hours every month turning dashboards into leadership commentary. This repository provides the starting point for an application that:

- accepts structured KPI CSV uploads,
- detects trend shifts and anomalies,
- generates executive summaries,
- prepares chart-to-text explanation hooks for multimodal workflows,
- recommends concrete follow-up actions.

## Current repository scope

This first version gives you a strong backend scaffold rather than a finished AI product. It includes:

- FastAPI service with health and report-generation endpoints,
- contract endpoints for input schema and workflow inspection,
- CSV ingestion, preprocessing, and KPI profiling,
- heuristic anomaly detection,
- trend-based narrative generation,
- chart explanation placeholder for future multimodal model support,
- test fixtures and baseline pytest coverage,
- Docker-ready packaging.

## Repository structure

```text
app/
  api/            FastAPI routes
  core/           settings and logging
  models/         response schemas
  services/       ingestion, analytics, anomaly detection, narrative pipeline
  prompts/        prompt artifacts for future LLM adapters
docs/             architecture notes
tests/            fixtures and baseline tests
scripts/          local development helpers
```

## Quick start

### 1. Create a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -e .[dev]
```

### 3. Run the API

```powershell
python -m uvicorn app.main:app --reload
```

Or use:

```powershell
.\scripts\run_dev.ps1
```

### 4. Run tests

```powershell
pytest
```

## API endpoints

### Health

`GET /api/v1/health`

### Generate report

`POST /api/v1/reports/generate`

Multipart form fields:

- `csv_file`: required CSV upload
- `report_title`: optional string
- `aggregation_granularity`: `weekly` or `monthly`
- `missing_value_strategy`: `drop`, `forward_fill`, or `interpolate`
- `chart_image`: optional image upload for multimodal chart explanation workflows

Expected CSV header:

```text
date,metric_name,value
```

### Input contract

`GET /api/v1/contracts/input-schema`

### Workflow definition

`GET /api/v1/contracts/workflow`

## Example response shape

```json
{
  "report_title": "Monthly Executive Performance Summary",
  "records_analyzed": 36,
  "periods_analyzed": 6,
  "date_column": "date",
  "preprocessing_summary": {
    "aggregation_granularity": "monthly",
    "missing_value_strategy": "forward_fill",
    "rows_received": 36,
    "exact_duplicate_rows_removed": 0,
    "date_metric_duplicates_collapsed": 0,
    "missing_values_detected": 0,
    "missing_values_imputed": 0,
    "output_periods_generated": 6
  },
  "executive_summary": "Monthly Executive Performance Summary covers 6 KPI(s)...",
  "trend_narrative": [
    "revenue closed at 520000.00..."
  ],
  "anomaly_commentary": [
    "revenue is flagged as medium severity..."
  ],
  "recommended_actions": [
    "Investigate the drivers behind the flagged anomalies before the next reporting cycle."
  ]
}
```

## Suggested next milestones

1. Add a real LLM provider adapter in `app/services/llm.py`.
2. Introduce model-specific prompt templates and evaluation datasets.
3. Add multimodal chart parsing with a vision-capable API.
4. Persist generated reports and feedback for iteration loops.
5. Add auth, observability, background jobs, and production deployment manifests.

## Tech stack

- Python
- FastAPI
- Pandas
- Matplotlib-ready workflow
- LLM integration abstraction
- Pytest

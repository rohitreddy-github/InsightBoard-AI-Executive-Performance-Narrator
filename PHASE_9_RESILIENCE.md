# Phase 9: Resiliency & Error Handling Implementation

## Overview
This phase implements production-grade error handling and resiliency patterns to ensure the application gracefully handles network failures, API rate limits, malformed inputs, and other edge cases.

## Key Implementations

### 1. LLM Call Retry Logic with Exponential Backoff

**Location:** `app/services/llm.py`

#### Changes:
- Added **Tenacity** library for sophisticated retry logic
- Implemented `@retry` decorator on LLM API calls with:
  - **Maximum 3 retry attempts** (configurable via `INSIGHTBOARD_LLM_MAX_RETRIES`)
  - **Exponential backoff**: 2s, 4s, 8s (with jitter)
  - **Grace period**: Minimum 2 seconds between retries

#### Key Classes Enhanced:
- `OpenAIResponsesLLMClient._generate_with_retry()` - Wraps OpenAI API calls
- `GeminiLLMClient._generate_with_retry()` - Wraps Gemini API calls

#### Retry Configuration:
```python
@retry(
    retry=retry_if_exception_type((Exception,)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
```

### 2. Enhanced CSV Ingestion Error Handling

**Location:** `app/services/ingestion.py`

#### Improvements:
- **Parse error detection**: Catches malformed CSV files early with descriptive messages
- **Empty file validation**: Rejects empty CSVs with guidance
- **Column validation**: Enhanced error messages listing required columns
- **Row validation**: Detailed error context showing validation failure count and samples
- **Date parsing errors**: Identifies problematic row indices and suggests format
- **Missing value handling**: Logs preprocessing statistics
- **Informative exceptions**: All errors include user-friendly guidance

#### Error Messages Example:
```
CSV columns must exactly match ['date', 'metric_name', 'value']. 
Received ['date', 'revenue']. 
Make sure your CSV has headers: 'date', 'metric_name', 'value'.
```

#### Logging:
- Added structured logging via Python `logging` module
- Logs successful ingestion with metrics: rows, metrics, duplicates removed, values imputed

### 3. Graceful Degradation

**Key Behavior:**
- LLM failures fall back to deterministic narrative generation
- Invalid CSVs raise informative `InputContractError` instead of generic exceptions
- Rate-limit handling via Tenacity exponential backoff
- Pipeline returns usable reports even when LLM API is unavailable

### 4. Configuration

**New Setting:** `llm_max_retries`
- Location: `app/core/config.py`
- Default: 3 retries
- Range: 1-10 retries
- Environment variable: `INSIGHTBOARD_LLM_MAX_RETRIES`

### 5. Dependencies

**Updated:** `pyproject.toml`
- Added `tenacity>=8.2.0,<9.0.0` dependency for retry logic

## Testing

### Comprehensive Test Suite

**Location:** `tests/test_resilience.py`

#### Test Categories:

**CSV Error Handling Tests:**
- Empty CSV rejection
- Malformed CSV handling
- Missing required columns detection
- Invalid date format identification
- Non-numeric value validation
- Headers-only CSV rejection
- Missing value imputation (forward-fill and interpolation)

**Pipeline Robustness Tests:**
- Invalid CSV error propagation
- LLM failure fallback behavior
- Anomaly detection edge case handling

**LLM Client Retry Configuration Tests:**
- Max retries parameter acceptance
- Settings propagation to clients

## Error Recovery Flow

```
┌─────────────────────────────────────────────────────┐
│           CSV Upload                                │
└────────────────┬────────────────────────────────────┘
                 │
        ┌────────▼────────┐
        │ Parse Check     │
        │ Column Validate │
        │ Row Validate    │
        └────────┬────────┘
                 │
        ┌────────▼────────────────────┐
        │ Preprocessing               │
        │ (Dedup, Impute, Aggregate)  │
        └────────┬────────────────────┘
                 │
        ┌────────▼────────────────────┐
        │ Analytics & Anomaly         │
        │ Detection                   │
        └────────┬────────────────────┘
                 │
        ┌────────▼────────────────────┐
        │ LLM Call (with retry)       │◄─── Attempts 1, 2, 3
        │                             │     (exp. backoff)
        └────────┬────────────────────┘
                 │
        ┌────────▼───────────────────────────┐
        │ LLM Success?                        │
        ├─────────────┬───────────────────────┤
        │ YES         │ NO (after 3 retries) │
        ▼             ▼                       │
    Narrative    Fallback Narrative           │
    ┌────────────────────────────────────────┘
    │
    ▼
✓ Report Response
```

## Usage

### No Action Required for Users
All error handling is automatic. Users simply:
1. Upload a CSV file
2. Receive either a generated report or an informative error

### Configuration (Optional)
To adjust retry behavior, set environment variable:
```bash
export INSIGHTBOARD_LLM_MAX_RETRIES=5
```

### Monitoring
- Check application logs for ingestion errors: `"CSV ingestion successful: ..."`
- LLM retry attempts logged as: `"OpenAI API call failed: ..."`
- Final fallback triggered: `"Failed to generate narrative sections after X attempts"`

## Testing Instructions

### Run resilience tests:
```bash
pytest tests/test_resilience.py -v
```

### Run all tests:
```bash
pytest tests/ -v
```

## Future Enhancements

1. **Circuit Breaker Pattern**: Disable LLM calls if failure rate exceeds threshold
2. **Request Queuing**: Queue requests during rate limit window (429 responses)
3. **Custom Backoff Strategies**: Support custom retry strategies per provider
4. **Metrics Collection**: Track retry success rates and latency
5. **Timeout Per Phase**: Implement per-stage timeouts instead of global timeout

## References

- **Tenacity Documentation**: https://tenacity.readthedocs.io/
- **Backoff Strategy**: Exponential backoff with jitter (AWS best practice)
- **Fallback Pattern**: Always provide degraded-but-functional output

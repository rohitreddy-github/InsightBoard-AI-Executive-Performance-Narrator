# Phase 3: Deterministic Anomaly Detection

## Overview

Phase 3 implements **deterministic anomaly detection** using rolling window z-score analysis. This approach ensures anomalies are flagged based on mathematical rigor rather than LLM guessing, providing:

- Provable, reproducible anomaly identification
- Precise dates and deviation metrics for each anomalous point
- Clear audit trail for executive reporting

## Architecture

### Core Components

#### 1. **AnomalyDataPoint** (Schema)
Represents a single anomalous data point with complete context:
- `date`: Exact date of the anomaly
- `value`: The anomalous value observed
- `rolling_mean`: 6-month (or configurable) rolling mean baseline
- `rolling_std`: 6-month rolling standard deviation
- `zscore`: Z-score calculation (value - mean) / std
- `deviation_percent`: Deviation as percentage of standard deviations

#### 2. **AnomalyDetector** (Service)
Implements rolling window z-score algorithm:

```
For each metric:
  1. Calculate rolling mean and std over window (default: 6 months)
  2. For each data point, compute z-score relative to rolling baseline
  3. Flag points where |zscore| >= threshold (default: 2.0)
  4. Return structured AnomalyInsight with all flagged points
```

### Algorithm Details

**Rolling Window Calculation:**
- Window size: 6 months (configurable via `anomaly_rolling_window` setting)
- Uses `pd.rolling(window=6, center=False)` for forward-looking baseline
- Avoids including current point in its own baseline (prevents self-contamination)

**Z-Score Threshold:**
- Default: ±2.0 standard deviations
- Rationale:  
  - ±2σ captures ~95% of normal variation in Gaussian distribution
  - Values at ±2.0 are statistically significant anomalies
  - Severity ladder:
    - |z| >= 3.0: HIGH
    - |z| >= 2.5: MEDIUM  
    - |z| >= 2.0: LOW

**Return Structure:**
```
AnomalyInsight:
  - metric: Name of KPI
  - severity: HIGH/MEDIUM/LOW based on max z-score
  - latest_value: Current value
  - baseline_value: Rolling mean at latest point
  - reason: Deterministic summary
  - anomalous_points: List of AnomalyDataPoint objects
    └─ Each point has date, value, rolling_mean, rolling_std, zscore, deviation_percent
```

## Configuration

Via `app/core/config.py`:

```python
anomaly_zscore_threshold: float = 2.0          # Z-score threshold
anomaly_rolling_window: int = 6                # Rolling window size (periods)
latest_change_alert_threshold: float = 0.15    # Fallback for point-to-point changes
```

Or environment variables:
```bash
INSIGHTBOARD_ANOMALY_ZSCORE_THRESHOLD=2.0
INSIGHTBOARD_ANOMALY_ROLLING_WINDOW=6
```

## Data Flow

1. **CSV Ingestion** → Data standardized to date/metric/value format
2. **Preprocessing** → Time series bucketed to monthly/weekly, missing values imputed
3. **Analytics** → KPIAnalyzer builds metric snapshots (trend, latest, mean, etc.)
4. **Anomaly Detection** → **AnomalyDetector.detect()** runs Phase 3:
   - Calculates rolling statistics
   - Computes z-scores for all points
   - Identifies anomalous points deterministically
5. **Narrative Generation** → LLM consumes *proven* anomalies to write explanations

## Key Design Principles

✓ **Deterministic**: No randomness, no LLM involved in detection  
✓ **Provable**: Every anomaly backed by mathematical calculation  
✓ **Precise**: Date and deviation metrics for each point  
✓ **Auditable**: Rolling statistics available for validation  
✓ **Efficient**: O(n) single-pass algorithm  

## Usage Example

```python
from app.services.anomaly import AnomalyDetector
from app.services.analytics import KPIAnalyzer

# Initialize detector
detector = AnomalyDetector(
    zscore_threshold=2.0,
    rolling_window=6,
    change_threshold=0.15,
)

# Detect anomalies
anomalies = detector.detect(dataset, metric_snapshots)

# Process results
for anomaly in anomalies:
    print(f"Metric: {anomaly.metric}")
    print(f"Severity: {anomaly.severity}")
    print(f"Baseline: ${anomaly.baseline_value:,.0f}")
    
    for point in anomaly.anomalous_points:
        print(f"  {point.date.strftime('%Y-%m-%d')}: "
              f"${point.value:,.0f} "
              f"(z={point.zscore:.2f}, "
              f"deviation={point.deviation_percent:.1f}%)")
```

## Testing

Run comprehensive anomaly detection tests:
```bash
python test_anomaly_detection.py
```

Output shows:
- Detected anomalies per metric
- List of anomalous points with dates
- Z-scores and deviation percentages
- Severity categorization

## What Gets Passed to LLM (Phase 4+)

The LLM receives *deterministic facts only*:
- Metric name
- Severity level (not derived, just categorized by z-score)
- List of exact dates with values and z-scores
- Baseline statistics

LLM's job: Write narrative explaining *why* these specific mathematical anomalies matter to the executive audience.

## Files Modified

- `app/models/schemas.py`: Added `AnomalyDataPoint` class
- `app/services/anomaly.py`: Rewrote `AnomalyDetector` with rolling z-score
- `app/core/config.py`: Added `anomaly_rolling_window` setting
- `app/services/pipeline.py`: Passes rolling window to detector
- `test_anomaly_detection.py`: Comprehensive test suite

## Next Steps (Phase 4+)

1. **Chart Explanation** → Multimodal analysis of visualizations
2. **Narrative Generation** → LLM writes business-aligned explanation
3. **Recommended Actions** → Strategic recommendations based on anomalies

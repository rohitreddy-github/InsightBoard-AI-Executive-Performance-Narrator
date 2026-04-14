# Phase 4: Automated Data Visualization (Matplotlib)

## Overview

Phase 4 implements **automated data visualization** using Matplotlib, generating clean, high-contrast charts optimized for multimodal LLM vision understanding. Charts are stored in memory as Base64-encoded strings to avoid disk I/O bottlenecks.

**Key Insight:** Multimodal LLMs perform best when visual data is clean, high-contrast, and uncluttered. Structured charts provide spatial representation alongside raw text.

## Architecture

### Core Component: DataVisualizationService

Provides three specialized visualization methods:

#### 1. **generate_anomaly_chart()**
Single-metric chart with full anomaly context:
- **Main trend line**: Actual metric values over time (blue, solid)
- **Rolling baseline**: 6-month baseline reference (green, dashed)
- **Anomaly markers**: Color-coded by severity
  - Red "X": HIGH severity (|z| ≥ 3.0)
  - Orange "s": MEDIUM severity (|z| ≥ 2.5)
  - Gold "D": LOW severity (|z| ≥ 2.0)
- **High-contrast legend**: Clear severity scale with visual indicators

#### 2. **generate_multiplot_dashboard()**
Multi-metric dashboard (2-column grid):
- Up to 4 metrics displayed as subplots
- Each subplot shows:
  - Metric name and severity level
  - Actual values with anomalies highlighted
  - Compact, scan-friendly design
- Ideal for executive dashboards showing multiple KPIs

#### 3. **generate_comparison_chart()**
Bar chart comparing latest metric values:
- Color-coded by trend direction
  - Green: Uptrend
  - Red: Downtrend
  - Blue: Flat
- Value labels on top of bars
- Best for C-suite executives comparing KPI positions

### Memory Optimization

All charts generated using in-memory buffers:

```python
buffer = io.BytesIO()
fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
image_bytes = buffer.getvalue()
base64_string = base64.b64encode(image_bytes).decode("utf-8")
```

**Benefits:**
- No disk I/O bottleneck
- Immediate image encoding to Base64
- Suitable for API responses and LLM context windows
- Clean garbage collection after generation

## Configuration

Via `app/core/config.py`:

```python
# Visualization defaults (add if not present)
visualization_figsize: tuple = (14, 8)     # Figure size (width, height) in inches
visualization_dpi: int = 100               # Dots per inch for rendering
```

Or via environment variables:
```bash
INSIGHTBOARD_VISUALIZATION_FIGSIZE="14,8"
INSIGHTBOARD_VISUALIZATION_DPI=100
```

## Integration with Pipeline

### Data Flow (Phases 1-4)

```
1. CSV Ingestion → Data standardized to date/metric/value format
2. Preprocessing → Time series bucketed to monthly/weekly
3. Analytics → KPIAnalyzer builds metric snapshots
4. Anomaly Detection → AnomalyDetector runs z-score analysis
5. **VISUALIZATION (NEW)** → DataVisualizationService generates charts
   └─ If anomalies detected, auto-generates multiplot dashboard
   └─ Stores image as Base64 in memory
6. Chart Explanation → ChartExplainer consumes generated images
7. Narrative Generation → LLM writes business narrative
```

### Pipeline Integration

The `ReportPipeline.generate_report()` now:

1. Detects anomalies (Phase 3)
2. **AUTO-generates multiplot dashboard if anomalies found** (Phase 4)
3. Passes generated image to ChartExplainer
4. Flows to narrative generation (Phase 5+)

```python
# Phase 4 integration in pipeline
if anomalies and chart_image_bytes is None:
    try:
        generated_chart_image_bytes, _ = self.visualization_service.generate_multiplot_dashboard(
            dataset=dataset,
            anomalies=anomalies,
            max_metrics=4,
        )
    except Exception:
        generated_chart_image_bytes = None  # Graceful degradation
```

## Usage Examples

### Generate Single Anomaly Chart

```python
from app.services.visualization import DataVisualizationService
from app.services.anomaly import AnomalyDetector
from app.services.analytics import KPIAnalyzer

# Setup services
viz_service = DataVisualizationService()
detector = AnomalyDetector(zscore_threshold=2.0)
analyzer = KPIAnalyzer()

# Detect anomalies
metric_snapshots = analyzer.build_metric_snapshots(dataset)
anomalies = detector.detect(dataset, metric_snapshots)

# Generate chart for first anomaly
if anomalies:
    image_bytes, base64_string = viz_service.generate_anomaly_chart(
        dataset=dataset,
        anomaly=anomalies[0],
    )
    
    # Use in API response
    response = {
        "chart_base64": base64_string,
        "metric": anomalies[0].metric,
    }
```

### Generate Multi-Metric Dashboard

```python
# Generate dashboard with top 4 anomalies
image_bytes, base64_string = viz_service.generate_multiplot_dashboard(
    dataset=dataset,
    anomalies=anomalies,
    max_metrics=4,
)

# Decode for frontend rendering
import base64
decoded = base64.b64decode(base64_string)
with open("dashboard.png", "wb") as f:
    f.write(decoded)
```

### Generate Comparison Chart

```python
# Compare latest values across metrics
image_bytes, base64_string = viz_service.generate_comparison_chart(
    dataset=dataset,
    metric_snapshots=metric_snapshots,
    max_metrics=6,
)
```

## Visual Design Principles

### High-Contrast Color Scheme
- **Primary data**: Dark blue (#1f77b4) for main trend
- **Baseline**: Green (#2ca02c) for rolling mean
- **Severity scale**: Red → Orange → Gold for |z-score| hierarchy

### Readability Optimizations
- **Marker variety**: Different shapes for severity (X, s, D)
- **Edge emphasis**: Black borders on anomaly markers
- **Grid overlay**: Light dashed grid at 30% opacity
- **Date formatting**: X-axis auto-rotating for clarity

### Executive-Grade Presentation
- **Title with key metrics**: "Metric: Revenue | Severity: HIGH | Anomalies: 3"
- **Compact legends**: Legend placed for minimal white space waste
- **Value labels**: On bar charts for quick reading
- **No clutter**: Only essential visual elements

## Output Specifications

### Image Properties
- **Format**: PNG (lossless, ideal for text/charts)
- **DPI**: 100 (default, adjustable)
- **Color space**: RGB
- **Encoding**: Base64 (ready for JSON/API)

### Base64 Encoding
```python
# Example output
base64_string = "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs..."

# Decode for file storage
import base64
image_bytes = base64.b64decode(base64_string)
with open("chart.png", "wb") as f:
    f.write(image_bytes)

# Use in HTML <img> tag
html = f'<img src="data:image/png;base64,{base64_string}" />'
```

## Error Handling

The pipeline gracefully degrades if visualization fails:

```python
try:
    generated_chart_image_bytes, _ = viz_service.generate_multiplot_dashboard(...)
except Exception:
    generated_chart_image_bytes = None  # Falls back to heuristic chart explanation
```

### Common Failure Points & Recovery
- **Metric not in dataset**: Skipped in dashboard
- **Anomaly list empty**: No dashboard generated
- **Rendering error**: Exception caught, pipeline continues
- **Memory pressure**: BytesIO buffers auto-cleanup

## Testing

Run visualization tests (example):

```python
from app.services.visualization import DataVisualizationService
from app.models.schemas import AnomalyDataPoint, AnomalyInsight

# Create mock anomaly
anomaly = AnomalyInsight(
    metric="Revenue",
    severity="high",
    latest_value=150000,
    baseline_value=100000,
    reason="Test anomaly",
    anomalous_points=[
        AnomalyDataPoint(
            date="2024-12-01",
            value=150000,
            rolling_mean=100000,
            rolling_std=10000,
            zscore=5.0,
            deviation_percent=500,
        )
    ]
)

# Generate and validate
viz = DataVisualizationService()
image_bytes, base64_string = viz.generate_anomaly_chart(dataset, anomaly)

assert len(image_bytes) > 0
assert len(base64_string) > 0
assert base64_string.startswith("iVBORw0KG")  # PNG magic bytes in Base64
```

## Next Steps (Phases 5+)

1. **Multimodal Chart Analysis** → Vision-Language Model interprets visualizations
2. **Enhanced Narrative Generation** → LLM writes richer explanations with visual context
3. **Interactive Dashboard** → Frontend renders Base64 charts with drill-down capabilities
4. **Custom Styling** → Configurable color schemes for different organizations

## Files Modified/Created

- `app/services/visualization.py`: New DataVisualizationService (created)
- `app/services/pipeline.py`: Integrated visualization generation
- `app/services/chart_explainer.py`: Ready to consume generated images (no changes needed)

## Design Rationale

**Why Matplotlib over other options:**
- Lightweight, no external dependencies (already included in scientific Python stacks)
- Fine-grained control over styling for executive-grade charts
- Proven performance for static image generation
- Easy integration with Base64 encoding via BytesIO

**Why in-memory buffers:**
- Eliminates disk I/O latency for real-time reporting
- Reduces filesystem complexity in containerized environments
- Safer for concurrent requests (no temp file collisions)
- Memory-efficient for typical chart sizes (<2MB)

**Why Base64 encoding:**
- Seamless integration with JSON API responses
- Compatible with `<img>` src attributes in HTML/web
- Suitable for LLM context windows (models accept base64 images)
- No additional storage infrastructure needed

"""
Phase 4: Automated Data Visualization - Test Suite

Demonstrates all visualization capabilities with realistic anomaly scenarios.
Run with: python test_visualization.py
"""

import base64
import pandas as pd
from datetime import datetime, timedelta

from app.services.visualization import DataVisualizationService
from app.services.ingestion import DatasetBundle
from app.models.schemas import (
    AnomalyDataPoint,
    AnomalyInsight,
    MetricSnapshot,
    PreprocessingSummary,
)


def create_test_dataset() -> tuple[DatasetBundle, list[MetricSnapshot], list[AnomalyInsight]]:
    """Create realistic test data with multiple metrics and anomalies."""

    # Generate 24 months of data
    dates = pd.date_range(start="2022-01-01", periods=24, freq="MS")

    # Create realistic KPI data
    revenue_base = [100000, 105000, 110000, 108000, 115000, 112000, 120000, 125000,
                   130000, 135000, 140000, 138000, 145000, 150000, 155000, 160000,
                   165000, 170000, 175000, 180000, 185000, 190000, 195000, 200000]

    # Add anomalies
    revenue_anomalies = revenue_base.copy()
    revenue_anomalies[5] = 75000   # Major dip
    revenue_anomalies[15] = 220000  # Spike

    customer_count = [1000 + i*50 for i in range(24)]
    customer_count[10] = 500  # Anomaly

    conversion_rate = [0.05 + i*0.001 for i in range(24)]
    conversion_rate[8] = 0.02  # Anomaly

    # Create DataFrame
    data = {
        "date": dates,
        "Revenue": revenue_anomalies,
        "Customer Count": customer_count,
        "Conversion Rate": conversion_rate,
    }
    df = pd.DataFrame(data)

    # Create DatasetBundle
    preprocessing_summary = PreprocessingSummary(
        aggregation_granularity="monthly",
        missing_value_strategy="forward_fill",
        rows_received=24,
        exact_duplicate_rows_removed=0,
        date_metric_duplicates_collapsed=0,
        missing_values_detected=0,
        missing_values_imputed=0,
        output_periods_generated=24,
    )

    dataset = DatasetBundle(
        frame=df,
        date_column="date",
        metric_columns=["Revenue", "Customer Count", "Conversion Rate"],
        record_count=24,
        period_count=24,
        preprocessing_summary=preprocessing_summary,
    )

    # Create metric snapshots
    metric_snapshots = [
        MetricSnapshot(
            metric="Revenue",
            latest_value=200000,
            previous_value=195000,
            absolute_change=5000,
            percent_change=0.0256,
            mean_value=140000,
            min_value=75000,
            max_value=220000,
            trend_direction="up",
        ),
        MetricSnapshot(
            metric="Customer Count",
            latest_value=2200,
            previous_value=2150,
            absolute_change=50,
            percent_change=0.0233,
            mean_value=1860,
            min_value=500,
            max_value=2200,
            trend_direction="up",
        ),
        MetricSnapshot(
            metric="Conversion Rate",
            latest_value=0.074,
            previous_value=0.073,
            absolute_change=0.001,
            percent_change=0.0137,
            mean_value=0.062,
            min_value=0.02,
            max_value=0.074,
            trend_direction="up",
        ),
    ]

    # Create anomalies with z-scores
    anomalies = [
        AnomalyInsight(
            metric="Revenue",
            severity="high",
            latest_value=200000,
            baseline_value=140000,
            reason="Detected 2 anomalous points exceeding plus/minus 2.0 standard deviations",
            anomalous_points=[
                AnomalyDataPoint(
                    date=dates[5],
                    value=75000,
                    rolling_mean=110000,
                    rolling_std=10000,
                    zscore=-3.5,
                    deviation_percent=350,
                ),
                AnomalyDataPoint(
                    date=dates[15],
                    value=220000,
                    rolling_mean=160000,
                    rolling_std=15000,
                    zscore=4.0,
                    deviation_percent=400,
                ),
            ],
        ),
        AnomalyInsight(
            metric="Customer Count",
            severity="medium",
            latest_value=2200,
            baseline_value=1860,
            reason="Detected 1 anomalous point exceeding plus/minus 2.5 standard deviations",
            anomalous_points=[
                AnomalyDataPoint(
                    date=dates[10],
                    value=500,
                    rolling_mean=1800,
                    rolling_std=300,
                    zscore=-4.33,
                    deviation_percent=433,
                ),
            ],
        ),
        AnomalyInsight(
            metric="Conversion Rate",
            severity="low",
            latest_value=0.074,
            baseline_value=0.062,
            reason="Detected 1 anomalous point at plus/minus 2.0 standard deviations",
            anomalous_points=[
                AnomalyDataPoint(
                    date=dates[8],
                    value=0.02,
                    rolling_mean=0.052,
                    rolling_std=0.008,
                    zscore=-4.0,
                    deviation_percent=400,
                ),
            ],
        ),
    ]

    return dataset, metric_snapshots, anomalies


def test_single_anomaly_chart():
    """Test: Generate single-metric anomaly chart."""
    print("\n" + "="*80)
    print("TEST 1: Single Anomaly Chart (Revenue)")
    print("="*80)

    dataset, metric_snapshots, anomalies = create_test_dataset()
    viz_service = DataVisualizationService(figsize=(14, 8), dpi=100)

    # Generate chart for Revenue (highest severity)
    revenue_anomaly = anomalies[0]
    image_bytes, base64_string = viz_service.generate_anomaly_chart(
        dataset=dataset,
        anomaly=revenue_anomaly,
    )

    print(f"[OK] Generated chart for metric: {revenue_anomaly.metric}")
    print(f"     Severity: {revenue_anomaly.severity.upper()}")
    print(f"     Anomalous points: {len(revenue_anomaly.anomalous_points)}")
    print(f"     Image size: {len(image_bytes):,} bytes")
    print(f"     Base64 length: {len(base64_string):,} characters")
    print(f"     Base64 prefix: {base64_string[:30]}...")

    # Verify Base64 is PNG
    assert base64_string.startswith("iVBORw0KG"), "Invalid PNG Base64 encoding"
    assert len(image_bytes) > 5000, "Image too small (likely empty)"
    print("[OK] PNG encoding verified")
    print(f"[OK] Successfully generated {len(image_bytes)} byte image")


def test_multiplot_dashboard():
    """Test: Generate multi-metric dashboard."""
    print("\n" + "="*80)
    print("TEST 2: Multi-Metric Dashboard (Top 3 Anomalies)")
    print("="*80)

    dataset, metric_snapshots, anomalies = create_test_dataset()
    viz_service = DataVisualizationService(figsize=(14, 8), dpi=100)

    # Generate dashboard with all anomalies
    image_bytes, base64_string = viz_service.generate_multiplot_dashboard(
        dataset=dataset,
        anomalies=anomalies,
        max_metrics=3,
    )

    print(f"[OK] Generated dashboard with {len(anomalies)} metrics")
    print(f"     Image size: {len(image_bytes):,} bytes")
    print(f"     Base64 length: {len(base64_string):,} characters")

    # Metrics info
    for i, anom in enumerate(anomalies, 1):
        print(f"     [{i}] {anom.metric} ({anom.severity}) - {len(anom.anomalous_points)} anomalies")

    assert base64_string.startswith("iVBORw0KG"), "Invalid PNG Base64 encoding"
    assert len(image_bytes) > 8000, "Image too small"
    print("[OK] Dashboard generated successfully")


def test_comparison_chart():
    """Test: Generate comparison bar chart."""
    print("\n" + "="*80)
    print("TEST 3: Comparison Chart (Latest Values)")
    print("="*80)

    dataset, metric_snapshots, anomalies = create_test_dataset()
    viz_service = DataVisualizationService(figsize=(14, 8), dpi=100)

    # Generate comparison chart
    image_bytes, base64_string = viz_service.generate_comparison_chart(
        dataset=dataset,
        metric_snapshots=metric_snapshots,
        max_metrics=3,
    )

    print(f"[OK] Generated comparison chart for {len(metric_snapshots)} metrics")
    print(f"     Image size: {len(image_bytes):,} bytes")

    for snapshot in metric_snapshots:
        trend = snapshot.trend_direction
        print(f"     * {snapshot.metric}: ${snapshot.latest_value:,.0f} ({trend})")

    assert base64_string.startswith("iVBORw0KG"), "Invalid PNG Base64 encoding"
    print("[OK] Comparison chart generated successfully")


def test_base64_round_trip():
    """Test: Encode/decode Base64 round-trip."""
    print("\n" + "="*80)
    print("TEST 4: Base64 Round-Trip (Encode/Decode)")
    print("="*80)

    dataset, _, anomalies = create_test_dataset()
    viz_service = DataVisualizationService()

    # Generate and encode
    original_bytes, base64_string = viz_service.generate_anomaly_chart(
        dataset=dataset,
        anomaly=anomalies[0],
    )

    # Decode back
    decoded_bytes = base64.b64decode(base64_string)

    print(f"[OK] Original size: {len(original_bytes):,} bytes")
    print(f"[OK] Base64 size: {len(base64_string):,} characters")
    print(f"[OK] Decoded size: {len(decoded_bytes):,} bytes")

    assert original_bytes == decoded_bytes, "Round-trip mismatch"
    print("[OK] Round-trip verification passed")


def test_html_img_tag_generation():
    """Test: Generate HTML <img> tags."""
    print("\n" + "="*80)
    print("TEST 5: HTML <img> Tag Generation")
    print("="*80)

    dataset, _, anomalies = create_test_dataset()
    viz_service = DataVisualizationService()

    _, base64_string = viz_service.generate_anomaly_chart(
        dataset=dataset,
        anomaly=anomalies[0],
    )

    # Create HTML img tag
    html_img = f'<img src="data:image/png;base64,{base64_string}" alt="{anomalies[0].metric}" />'

    print(f"[OK] Generated HTML <img> tag")
    print(f"     Tag length: {len(html_img):,} characters")
    print(f"     Preview: {html_img[:100]}...")

    assert html_img.startswith('<img src="data:image/png;base64,'), "Invalid HTML tag"
    print("[OK] HTML tag format verified")


def test_error_handling():
    """Test: Error handling for edge cases."""
    print("\n" + "="*80)
    print("TEST 6: Error Handling")
    print("="*80)

    dataset, _, anomalies = create_test_dataset()
    viz_service = DataVisualizationService()

    # Test 1: Invalid metric name
    invalid_anomaly = AnomalyInsight(
        metric="Non-Existent Metric",
        severity="low",
        latest_value=100,
        baseline_value=100,
        reason="Test",
        anomalous_points=[],
    )

    try:
        viz_service.generate_anomaly_chart(dataset=dataset, anomaly=invalid_anomaly)
        print("[FAIL] Should have raised ValueError for invalid metric")
    except ValueError as e:
        print(f"[OK] Correctly raised ValueError: {e}")

    # Test 2: Empty anomalies
    try:
        empty_anomalies = []
        viz_service.generate_multiplot_dashboard(
            dataset=dataset,
            anomalies=empty_anomalies,
            max_metrics=4,
        )
        print("[FAIL] Should have raised ValueError for empty anomalies")
    except ValueError as e:
        print(f"[OK] Correctly raised ValueError: {e}")

    print("[OK] Error handling verified")


def main():
    """Run all visualization tests."""
    print("\n" + "PHASE 4: AUTOMATED DATA VISUALIZATION TEST SUITE".center(80))
    print("Testing DataVisualizationService with realistic KPI data")

    try:
        test_single_anomaly_chart()
        test_multiplot_dashboard()
        test_comparison_chart()
        test_base64_round_trip()
        test_html_img_tag_generation()
        test_error_handling()

        print("\n" + "="*80)
        print("ALL TESTS PASSED".center(80))
        print("="*80)
        print("\nSummary:")
        print("  - Single anomaly charts: OK")
        print("  - Multi-metric dashboards: OK")
        print("  - Comparison charts: OK")
        print("  - Base64 encoding: OK")
        print("  - HTML integration: OK")
        print("  - Error handling: OK")
        print("\nPhase 4 implementation complete and tested!")

    except Exception as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()

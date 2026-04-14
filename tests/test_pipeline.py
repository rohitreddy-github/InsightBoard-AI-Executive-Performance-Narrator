from app.services.pipeline import build_report_pipeline


def test_report_pipeline_generates_summary(sample_csv_bytes: bytes) -> None:
    pipeline = build_report_pipeline()

    result = pipeline.generate_report(
        report_title="Monthly Executive Performance Summary",
        csv_bytes=sample_csv_bytes,
        source_name="monthly_kpis.csv",
    )

    assert result.records_analyzed == 36
    assert result.periods_analyzed == 6
    assert result.date_column == "date"
    assert result.preprocessing_summary.aggregation_granularity == "monthly"
    assert result.metric_snapshots
    assert result.executive_summary
    assert result.recommended_actions


def test_report_endpoint_accepts_csv_upload(client, sample_csv_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/reports/generate",
        data={"report_title": "Board KPI Summary"},
        files={"csv_file": ("monthly_kpis.csv", sample_csv_bytes, "text/csv")},
    )

    body = response.json()

    assert response.status_code == 201
    assert body["report_title"] == "Board KPI Summary"
    assert body["records_analyzed"] == 36
    assert body["periods_analyzed"] == 6
    assert body["preprocessing_summary"]["aggregation_granularity"] == "monthly"
    assert len(body["metric_snapshots"]) >= 1


def test_report_endpoint_rejects_invalid_contract(client) -> None:
    invalid_csv = b"month,revenue\n2025-01-01,100"

    response = client.post(
        "/api/v1/reports/generate",
        files={"csv_file": ("invalid.csv", invalid_csv, "text/csv")},
    )

    assert response.status_code == 422
    assert "date" in response.json()["detail"]


def test_pipeline_preprocesses_dirty_daily_data(dirty_daily_csv_bytes: bytes) -> None:
    pipeline = build_report_pipeline()

    result = pipeline.generate_report(
        report_title="Weekly Operations Review",
        csv_bytes=dirty_daily_csv_bytes,
        source_name="dirty_daily_kpis.csv",
        aggregation_granularity="weekly",
        missing_value_strategy="interpolate",
    )

    assert result.records_analyzed == 12
    assert result.periods_analyzed >= 2
    assert result.preprocessing_summary.exact_duplicate_rows_removed == 1
    assert result.preprocessing_summary.missing_values_detected == 2
    assert result.preprocessing_summary.missing_values_imputed >= 2
    assert result.preprocessing_summary.aggregation_granularity == "weekly"
    assert result.preprocessing_summary.missing_value_strategy == "interpolate"


def test_report_endpoint_accepts_preprocessing_options(client, dirty_daily_csv_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/reports/generate",
        data={
            "report_title": "Weekly Operations Review",
            "aggregation_granularity": "weekly",
            "missing_value_strategy": "forward_fill",
        },
        files={"csv_file": ("dirty_daily_kpis.csv", dirty_daily_csv_bytes, "text/csv")},
    )

    body = response.json()

    assert response.status_code == 201
    assert body["preprocessing_summary"]["aggregation_granularity"] == "weekly"
    assert body["preprocessing_summary"]["missing_value_strategy"] == "forward_fill"

def test_input_schema_endpoint_returns_canonical_contract(client) -> None:
    response = client.get("/api/v1/contracts/input-schema")

    body = response.json()

    assert response.status_code == 200
    assert body["format"] == "long"
    assert body["allowed_columns"] == ["date", "metric_name", "value"]


def test_workflow_endpoint_returns_phase_one_architecture(client) -> None:
    response = client.get("/api/v1/contracts/workflow")

    body = response.json()

    assert response.status_code == 200
    assert body["stages"][0]["name"] == "ingestion"
    assert body["stages"][-1]["name"] == "output"

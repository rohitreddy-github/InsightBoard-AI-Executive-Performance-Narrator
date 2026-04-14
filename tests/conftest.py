from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_csv_bytes() -> bytes:
    fixture_path = Path(__file__).parent / "fixtures" / "monthly_kpis.csv"
    return fixture_path.read_bytes()


@pytest.fixture
def dirty_daily_csv_bytes() -> bytes:
    fixture_path = Path(__file__).parent / "fixtures" / "dirty_daily_kpis.csv"
    return fixture_path.read_bytes()

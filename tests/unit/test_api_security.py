from fastapi.testclient import TestClient
import pandas as pd

from api import main as api
from api.main import app
from config import settings


VALID_SITUATION = {
    "driver_number": 1, "lap_number": 10, "lap_duration": 90.0,
    "tyre_compound": "MEDIUM", "tyre_age_laps": 8, "should_pit_soon": False,
}


def test_protected_ai_endpoint_rejects_missing_service_key(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "SERVICE_API_KEY", "test-secret")
    response = TestClient(app).post("/strategy", json=VALID_SITUATION)
    assert response.status_code == 401


def test_health_exposes_states_without_secret_values(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_API_KEY", "test-secret")
    payload = TestClient(app).get("/health").json()
    assert "checks" in payload
    assert "test-secret" not in str(payload)


def test_laps_response_excludes_unconsumed_feature_columns(monkeypatch):
    api._laps_cache.clear()
    frame = pd.DataFrame({
        "driver_number": [1],
        "lap_number": [1],
        "lap_duration": [91.2],
        "tyre_compound": ["MEDIUM"],
        "tyre_age_laps": [1],
        "tyre_degradation_rate": [0.0],
        "rolling_avg_lap_time": [91.2],
        "lap_delta": [0.0],
        "should_pit_soon": [False],
        "estimated_laps_to_pit": [999.0],
        "stint_length": [1],
        "internal_feature": ["must-not-leak"],
    })
    monkeypatch.setattr(api, "_load_race_frame", lambda _year, _round: frame)

    response = TestClient(app).get("/race/2099/1/laps")

    assert response.status_code == 200
    assert response.json()[0]["driver_number"] == 1
    assert "internal_feature" not in response.json()[0]

from fastapi.testclient import TestClient

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

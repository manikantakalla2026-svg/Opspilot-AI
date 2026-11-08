from fastapi.testclient import TestClient
from app.main import app, settings

client = TestClient(app)


def test_liveness():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unconfigured_database_is_not_reported_as_healthy(monkeypatch):
    monkeypatch.setattr(settings, "database_url", None)
    response = client.get("/health/db")
    assert response.status_code == 503
    assert response.json() == {"status": "not_configured"}


def test_cors_allows_frontend_only():
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.get("/health", headers={"Origin": "https://unknown.example"})
    assert "access-control-allow-origin" not in denied.headers

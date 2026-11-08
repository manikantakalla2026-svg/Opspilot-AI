"""Real PostgreSQL integration tests; run only with RUN_NEON_TESTS=1.

Uses the ignored test branch file, never the production settings URL.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from db_safety import assert_isolated
from app.core.config import settings
from app.db.session import build_engine, get_session
from app.main import app
from app.models.entities import Incident, Log, Service, utcnow

pytestmark = pytest.mark.skipif(os.getenv("RUN_NEON_TESTS") != "1", reason="Requires isolated Neon test branch")


@pytest.fixture
def workspace(monkeypatch):
    path = Path(__file__).resolve().parents[1] / ".env.test.local"
    url = dotenv_values(path).get("DATABASE_URL")
    assert url, "Create .env.test.local for an isolated branch first"
    assert_isolated(url, settings.database_url.get_secret_value() if settings.database_url else None)
    engine = build_engine(SecretStr(url))

    def test_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    monkeypatch.setattr(settings, "workspace_token", SecretStr("test-workspace-token"))
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as client:
        client.headers["X-Workspace-Token"] = "test-workspace-token"
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def create(client):
    response = client.post("/services", json={"name": f"test-{uuid4().hex[:12]}", "description": "integration verification"})
    assert response.status_code == 201, response.text
    return response.json()


def send(client, service, **overrides):
    return client.post(f"/ingest/{service['id']}", headers={"X-Ingestion-Key": service["ingestion_key"]}, json={
        "severity": "ERROR", "message": "Payment timed out after 30 seconds", "error_type": "GatewayTimeout",
        "endpoint": "/checkout", **overrides})


def test_service_crud_auth_and_key_rotation(workspace):
    client, _ = workspace
    assert client.get("/services", headers={"X-Workspace-Token": "wrong"}).status_code == 401
    service = create(client)
    assert "ingestion_key_hash" not in service
    detail = client.get(f"/services/{service['id']}").json()
    assert "ingestion_key" not in detail
    assert client.post("/services", json={"name": service["name"]}).status_code == 409
    assert client.put(f"/services/{service['id']}", json={"name": service["name"], "description": "updated"}).status_code == 200
    assert client.get(f"/services/{service['id']}").json()["description"] == "updated"
    assert client.post(f"/ingest/{service['id']}", json={"severity": "INFO", "message": "hello"}).status_code == 401
    new_key = client.post(f"/services/{service['id']}/rotate-key").json()["ingestion_key"]
    assert send(client, service).status_code == 401
    service["ingestion_key"] = new_key
    assert send(client, service).status_code == 201
    assert client.delete(f"/services/{service['id']}").status_code == 204
    assert send(client, service).status_code == 409
    assert not client.get(f"/services/{service['id']}").json()["active"]


def test_threshold_persistence_sanitization_filters_and_resolution(workspace):
    client, engine = workspace
    service = create(client)
    for i in range(4):
        response = send(client, service)
        assert response.status_code == 201, response.text
        assert response.json()["incident_id"] is None
    response = send(client, service, metadata={"password": "do-not-store", "nested": {"api_key": "sensitive"}})
    incident_id = response.json()["incident_id"]
    assert incident_id
    assert send(client, service).json()["incident_id"] == incident_id
    with Session(engine) as session:
        incident = session.get(Incident, incident_id)
        assert incident.event_count == 6
        assert session.scalar(select(func.count()).select_from(Log).where(Log.service_id == service["id"])) == 6
    response = client.get(f"/logs?service_id={service['id']}&severity=ERROR&q=timed&limit=2&offset=2")
    assert response.json()["total"] == 6
    assert len(response.json()["items"]) == 2
    records = client.get(f"/logs?service_id={service['id']}").json()["items"]
    metadata = next(r["metadata"] for r in records if r["metadata"])
    assert metadata["password"] == "[REDACTED]"
    assert metadata["nested"]["api_key"] == "[REDACTED]"
    assert client.patch(f"/incidents/{incident_id}", json={"status": "Investigating"}).status_code == 200
    assert client.patch(f"/incidents/{incident_id}", json={"status": "Resolved"}).status_code == 200
    for _ in range(4):
        assert send(client, service).json()["incident_id"] is None
    new_id = send(client, service).json()["incident_id"]
    assert new_id and new_id != incident_id
    assert client.patch(f"/incidents/{incident_id}", json={"status": "Open"}).status_code == 409


def test_concurrent_ingestion_creates_one_incident(workspace):
    client, engine = workspace
    service = create(client)
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda _: send(client, service), range(10)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    with Session(engine) as session:
        incidents = session.scalars(select(Incident).where(Incident.service_id == service["id"])).all()
        assert len(incidents) == 1
        assert incidents[0].event_count == 10


def test_window_excludes_old_logs_and_info_never_triggers(workspace):
    client, engine = workspace
    service = create(client)
    for _ in range(4):
        assert send(client, service).status_code == 201
    with Session(engine) as session:
        session.execute(update(Log).where(Log.service_id == service["id"]).values(received_at=utcnow() - timedelta(minutes=3)))
        session.commit()
    assert send(client, service).json()["incident_id"] is None
    for _ in range(6):
        assert send(client, service, severity="INFO").json()["incident_id"] is None


def test_simulator_cooldown_and_dashboard(workspace):
    client, _ = workspace
    service = create(client)
    response = client.post("/simulator", json={"service_id": service["id"], "scenario": "payment_timeout"})
    assert response.status_code == 201, response.text
    assert response.json()["logs_created"] == 5
    assert response.json()["incident_id"]
    assert client.post("/simulator", json={"service_id": service["id"], "scenario": "normal"}).status_code == 429
    metrics = client.get("/dashboard").json()
    assert metrics["errors_24h"] >= 5
    assert metrics["unhealthy"] >= 1
    assert metrics["active_incidents"] >= 1
    assert metrics["trend"]


def test_validation_redaction_and_isolation(workspace):
    client, _ = workspace
    service = create(client)
    other = create(client)
    assert send(client, {**service, "ingestion_key": other["ingestion_key"]}).status_code == 401
    response = send(client, service, severity="INVALID", metadata={"token": "secret-value"})
    assert response.status_code == 422
    assert "secret-value" not in response.text
    assert send(client, service, timestamp="2026-01-01T10:00:00").status_code == 422
    assert client.get("/logs?limit=101").status_code == 422
    assert send(client, service, message="password=hidden api_key=private Bearer abc123 user@example.com", endpoint="/checkout?token=private").status_code == 201
    log = client.get(f"/logs?service_id={service['id']}").json()["items"][0]
    assert "hidden" not in log["message"] and "private" not in log["message"]
    assert "abc123" not in log["message"] and "user@example.com" not in log["message"]
    assert log["endpoint"] == "/checkout"


def test_rate_limit_is_persisted_and_normal_simulation_is_healthy(workspace):
    client, engine = workspace
    service = create(client)
    result = client.post("/simulator", json={"service_id": service["id"], "scenario": "normal"})
    assert result.status_code == 201
    assert result.json()["logs_created"] == 3
    assert result.json()["incident_id"] is None
    with Session(engine) as session:
        now = utcnow()
        session.add_all([Log(service_id=service["id"], timestamp=now, received_at=now,
                             severity="INFO", message="Rate limit fixture", signature="fixture")
                         for _ in range(117)])
        session.commit()
    assert send(client, service).status_code == 429
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Log).where(Log.service_id == service["id"])) == 120


def test_services_do_not_share_incidents_and_critical_escalates(workspace):
    client, _ = workspace
    first, second = create(client), create(client)
    for _ in range(4):
        assert send(client, first).json()["incident_id"] is None
    assert send(client, second).json()["incident_id"] is None
    incident = send(client, first, severity="CRITICAL").json()["incident_id"]
    assert incident
    rows = client.get(f"/incidents?service_id={first['id']}").json()["items"]
    assert rows[0]["severity"] == "CRITICAL"
    assert rows[0]["event_count"] == 5
    assert not client.get(f"/incidents?service_id={second['id']}").json()["items"]


def test_quickcart_evidence_and_independent_persistence(workspace):
    client, engine = workspace
    service = create(client)
    response = client.post('/simulator', json={'service_id': service['id'], 'scenario': 'payment_timeout'})
    assert response.status_code == 201
    incident_id = response.json()['incident_id']
    assert incident_id and response.json()['logs_created'] == 5
    # A new SQLAlchemy session reads committed records independently of the API.
    with Session(engine) as session:
        stored = session.get(Incident, incident_id)
        assert stored.event_count == 5
        rows = session.scalars(select(Log).where(Log.service_id == service['id'])).all()
        assert len(rows) == 5
        log_id = str(rows[0].id)
    logs = client.get(f"/logs?service_id={service['id']}").json()
    assert logs['total'] == 5
    assert any(i['id'] == incident_id for i in client.get('/incidents?limit=100').json()['items'])
    assert client.get('/dashboard').json()['active_incidents'] >= 1
    path = f'/incidents/{incident_id}/evidence/{log_id}'
    evidence = client.get(path)
    assert evidence.status_code == 200 and evidence.json()['id'] == log_id
    assert evidence.json()['message'] == 'Payment gateway timed out after 30 seconds'
    assert client.get(path, headers={'X-Workspace-Token': 'wrong'}).status_code == 401
    other = create(client)
    other_incident = client.post('/simulator', json={'service_id': other['id'], 'scenario': 'exception'}).json()['incident_id']
    assert client.get(f'/incidents/{other_incident}/evidence/{log_id}').status_code == 404
    assert client.get(f'/incidents/{incident_id}/evidence/{uuid4()}').status_code == 404
    # Normal simulator events still do not open an incident.
    normal = create(client)
    result = client.post('/simulator', json={'service_id': normal['id'], 'scenario': 'normal'})
    assert result.json()['incident_id'] is None and result.json()['logs_created'] == 3

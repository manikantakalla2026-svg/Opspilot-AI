"""SDK -> actual ingestion route -> isolated PostgreSQL, opt-in only."""
import json
import sys
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from test_operations import workspace, create, pytestmark
from app.models.entities import Incident, Log

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "opspilot-sdk" / "src"))
from opspilot_sdk import OpsPilot


def test_sdk_five_errors_create_persisted_incident(workspace):
    api, engine = workspace
    service = create(api)
    replies = []
    def ingest(request):
        response = api.post(request.url.path, headers={"X-Ingestion-Key": request.headers["X-Ingestion-Key"]},
                            json=json.loads(request.content))
        replies.append(response)
        return httpx.Response(response.status_code, json=response.json())
    sdk = OpsPilot("http://127.0.0.1:8000", service["id"], service["ingestion_key"],
                   transport=httpx.MockTransport(ingest))
    try:
        for _ in range(4):
            assert sdk.report_exception(RuntimeError("private message"), endpoint="/checkout")
        assert sdk.flush(30)
        assert len(replies) == 4
        assert all(r.status_code == 201 and r.json()["incident_id"] is None for r in replies)
        assert sdk.report_exception(RuntimeError("private message"), endpoint="/checkout")
        assert sdk.flush(30)
        incident_id = replies[-1].json()["incident_id"]
        assert replies[-1].status_code == 201 and incident_id
        with Session(engine) as session:
            from uuid import UUID
            incident = session.get(Incident, UUID(incident_id))
            assert incident.event_count == 5 and incident.status == "Open"
            assert (incident.last_seen - incident.first_seen).total_seconds() <= 120
            logs = session.scalars(select(Log).where(Log.service_id == UUID(service["id"]))).all()
            assert len(logs) == 5
            assert all(log.message == "Unhandled RuntimeError" for log in logs)
        assert sdk.stats["delivered"] == 5
    finally:
        sdk.close()

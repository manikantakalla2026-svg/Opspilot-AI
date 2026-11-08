"""Live demo verification. Creates a QuickCart service and real demo data."""
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from sqlalchemy import func, inspect, select
from app.core.config import settings
from app.db.session import engine
from app.models.entities import Incident, Log, Service

base = 'http://127.0.0.1:5173/api'
headers = {'X-Workspace-Token': settings.workspace_token.get_secret_value()}
with httpx.Client(base_url=base, headers=headers, timeout=30) as client:
    assert client.get('/health/db').json()['status'] == 'ok'
    assert client.get('/services', headers={'X-Workspace-Token': ''}).status_code == 401
    response = client.post('/services', json={'name': 'QuickCart Payments', 'description': 'Bounded payment-service demonstration; real persisted demo events'})
    if response.status_code == 201:
        service = response.json()
        result = client.post(f"/ingest/{service['id']}", headers={'X-Ingestion-Key': service['ingestion_key']}, json={'severity': 'INFO', 'message': 'QuickCart payment service initialized', 'endpoint': '/payments/checkout', 'metadata': {'source': 'demo_verification'}})
        assert result.status_code == 201, result.text
    else:
        assert response.status_code == 409, response.text
        service = next(s for s in client.get('/services?limit=100').json()['items'] if s['name'] == 'QuickCart Payments')
    result = client.post('/simulator', json={'service_id': service['id'], 'scenario': 'payment_timeout'})
    assert result.status_code == 201, result.text
    assert result.json()['logs_created'] == 5
    assert result.json()['incident_id']
    logs = client.get(f"/logs?service_id={service['id']}").json()
    incidents = client.get(f"/incidents?service_id={service['id']}").json()
    metrics = client.get('/dashboard').json()
    assert logs['total'] >= 5 and incidents['total'] >= 1
    assert metrics['active_incidents'] >= 1 and metrics['errors_24h'] >= 5
    print('HTTP frontend proxy: service CRUD, authenticated ingestion, simulator, logs, incidents, dashboard PASS')
    print(f"QuickCart: {logs['total']} persisted logs; {incidents['total']} incident(s); {metrics['errors_24h']} errors / 24h")
with engine().connect() as connection:
    print('Neon tables:', ', '.join(inspect(connection).get_table_names()))
    count = connection.scalar(select(func.count()).select_from(Log).where(Log.service_id == UUID(service['id'])))
    assert count >= 5
    print('Independent Neon connection: persisted logs verified:', count)
print('LIVE WORKFLOW PASS')

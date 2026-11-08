"""Verify HTTP proxy -> simulator -> PostgreSQL -> analysis/evidence on TEST DB only.
Start demo_test_server.py and Vite port 5174 with DEV_API_TARGET first.
Use --resume after restarting the isolated API to verify durable persistence.
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
from uuid import uuid4
from dotenv import dotenv_values
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import SecretStr
from app.core.config import settings
from app.db.session import build_engine
from app.models.entities import Incident, Log
from db_safety import assert_isolated
import httpx

values = dotenv_values(Path(__file__).resolve().parents[1] / '.env.test.local')
assert_isolated(values.get('DATABASE_URL'), settings.database_url.get_secret_value())
state_path = Path(__file__).resolve().parents[1] / '.demo-verification.local.json'
with httpx.Client(base_url='http://127.0.0.1:5174/api',
        headers={'X-Workspace-Token': 'opspilot-browser-test'}, timeout=30) as client:
    def request(method, path, body=None):
        response = client.request(method, path, json=body)
        assert response.is_success, f'{path}: {response.status_code}'
        return response.json()
    if '--resume' in sys.argv:
        saved = json.loads(state_path.read_text())
        service_id, incident_id = saved['service_id'], saved['incident_id']
    else:
        service = request('POST', '/services', {'name': 'Interview-QuickCart-' + uuid4().hex[:8]})
        service_id = service['id']
        simulation = request('POST', '/simulator', {'service_id': service_id, 'scenario': 'payment_timeout'})
        assert simulation['logs_created'] == 5
        incident_id = simulation['incident_id']
        result = request('POST', f'/incidents/{incident_id}/analysis', {'simulated': True})
        assert result['simulated'] and result['source'] == 'Simulated analysis'
        assert result['evidence'][0]['category'] == 'payment_timeout'
        evidence_id = result['analysis']['hypotheses'][0]['evidence_ids'][0]
        evidence = request('GET', f'/incidents/{incident_id}/evidence/{evidence_id}')
        assert evidence['message'] == 'Payment gateway timed out after 30 seconds'
        state_path.write_text(json.dumps({'service_id': service_id, 'incident_id': incident_id}))
        print('Simulator, simulated analysis label, classification and stored evidence HTTP checks passed.')
    assert request('GET', f'/logs?service_id={service_id}')['total'] == 5
    assert request('GET', f'/incidents?service_id={service_id}')['items'][0]['id'] == incident_id
    assert request('GET', '/dashboard')['active_incidents'] >= 1
    engine = build_engine(SecretStr(values['DATABASE_URL']))
    with Session(engine) as independent:
        assert independent.get(Incident, incident_id).event_count == 5
        assert independent.scalar(select(func.count()).select_from(Log).where(Log.service_id == service_id)) == 5
    engine.dispose()
    print('Independent PostgreSQL persistence and dashboard checks passed' + (' after API restart.' if '--resume' in sys.argv else '.'))

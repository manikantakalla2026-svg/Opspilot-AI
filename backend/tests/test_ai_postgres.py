"""PostgreSQL endpoint, cache and concurrent quota integration tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID
import pytest
from pydantic import SecretStr
from sqlalchemy import update, delete
from sqlalchemy.orm import Session
from test_operations import workspace, create, send, pytestmark
from app.core.config import settings
from app.models.entities import AIUsage, AIAnalysis, Log, utcnow
from app.services.ai_providers import demo_analysis


def setup_ai(workspace, monkeypatch):
    client, engine = workspace
    with Session(engine) as session:
        session.execute(delete(AIAnalysis))
        session.execute(delete(AIUsage))
        session.commit()
    monkeypatch.setattr(settings, 'gemini_api_key', SecretStr('fake'))
    monkeypatch.setattr(settings, 'ai_external_enabled', True)
    service = create(client)
    for _ in range(5):
        incident = send(client, service).json()['incident_id']
    return client, engine, service, incident


def cooldown(engine):
    with Session(engine) as session:
        session.execute(update(AIUsage).values(last_request=utcnow()-timedelta(minutes=2)))
        session.commit()


def test_endpoint_cache_quota_and_changed_evidence(workspace, monkeypatch):
    client, engine, service, incident = setup_ai(workspace, monkeypatch)
    calls = []
    def fake(self, evidence):
        calls.append(evidence)
        return demo_analysis(evidence)
    monkeypatch.setattr('app.api.analysis.GeminiProvider.analyze', fake)
    path = f'/incidents/{incident}/analysis'
    assert client.post(path, json={'consent': True}).status_code == 200
    assert client.post(path, json={'consent': True}).status_code == 429
    cooldown(engine)
    assert client.post(path, json={'consent': True}).json()['cached']
    assert len(calls) == 1
    assert all(set(e) == {'id', 'severity', 'category'} for e in calls[0])
    send(client, service)
    cooldown(engine)
    assert not client.post(path, json={'consent': True}).json()['cached']
    assert len(calls) == 2
    monkeypatch.setattr(settings, 'ai_global_daily_request_limit', 3)
    cooldown(engine)
    assert client.post(path, json={'simulated': True}).status_code == 429
    assert client.get('/dashboard').status_code == 200


def test_missing_key_consent_and_demo(workspace, monkeypatch):
    client, engine, _, incident = setup_ai(workspace, monkeypatch)
    path = f'/incidents/{incident}/analysis'
    assert client.post(path, json={}).status_code == 403
    cooldown(engine)
    monkeypatch.setattr(settings, 'gemini_api_key', None)
    assert client.post(path, json={'consent': True}).status_code == 503
    cooldown(engine)
    result = client.post(path, json={'simulated': True}).json()
    assert result['simulated'] and result['source'] == 'Simulated analysis'
    assert result['quota']['investigations_remaining'] == settings.ai_daily_investigation_limit


def test_concurrent_requests_cannot_bypass_quota(workspace, monkeypatch):
    client, engine, _, incident = setup_ai(workspace, monkeypatch)
    monkeypatch.setattr(settings, 'ai_daily_investigation_limit', 1)
    monkeypatch.setattr('app.api.analysis.GeminiProvider.analyze', lambda self, e: demo_analysis(e))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post(f'/incidents/{incident}/analysis', json={'consent': True}).status_code, range(4)))
    assert results.count(200) == 1
    assert results.count(429) == 3
    cooldown(engine)
    # Cache still works after the daily investigation allowance is exhausted.
    assert client.post(f'/incidents/{incident}/analysis', json={'consent': True}).json()['cached']


def test_invalid_evidence_and_provider_failures_charge_quota(workspace, monkeypatch):
    client, engine, _, incident = setup_ai(workspace, monkeypatch)
    def invalid(self, evidence):
        result = demo_analysis(evidence)
        result.hypotheses[0].evidence_ids = ['not-this-incident']
        return result
    monkeypatch.setattr('app.api.analysis.GeminiProvider.analyze', invalid)
    path = f'/incidents/{incident}/analysis'
    assert client.post(path, json={'consent': True}).status_code == 502
    assert client.get('/ai/quota').json()['investigations_remaining'] == settings.ai_daily_investigation_limit - 1
    cooldown(engine)
    assert client.post(path, json={'consent': True}).status_code == 409
    assert client.get('/dashboard').status_code == 200


def test_daily_reset_and_investigation_limit(workspace, monkeypatch):
    client, engine, service, incident = setup_ai(workspace, monkeypatch)
    monkeypatch.setattr(settings, 'ai_daily_investigation_limit', 0)
    path = f'/incidents/{incident}/analysis'
    assert client.post(path, json={'consent': True}).status_code == 429
    with Session(engine) as session:
        session.execute(update(AIUsage).values(day='2000-01-01', requests=9999, investigations=9999,
            last_request=utcnow()-timedelta(minutes=2)))
        session.commit()
    monkeypatch.setattr(settings, 'ai_daily_investigation_limit', 1)
    monkeypatch.setattr('app.api.analysis.GeminiProvider.analyze', lambda self, e: demo_analysis(e))
    assert client.post(path, json={'consent': True}).status_code == 200
    send(client, service)
    cooldown(engine)
    assert client.post(path, json={'consent': True}).status_code == 429


def test_provider_429_endpoint_keeps_dashboard_available(workspace, monkeypatch):
    from fastapi import HTTPException
    client, engine, _, incident = setup_ai(workspace, monkeypatch)
    def exhausted(self, evidence):
        raise HTTPException(429, 'Gemini rate limit reached')
    monkeypatch.setattr('app.api.analysis.GeminiProvider.analyze', exhausted)
    assert client.post(f'/incidents/{incident}/analysis', json={'consent': True}).status_code == 429
    assert client.get('/ai/quota').json()['investigations_remaining'] == settings.ai_daily_investigation_limit - 1
    assert client.get('/dashboard').status_code == 200

"""Single demo workspace investigations with durable, shared PostgreSQL limits."""
import hashlib
import json
import re
from datetime import timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import require_workspace
from app.db.session import get_session
from app.models.entities import AIAnalysis, AIUsage, Incident, Log, utcnow
from app.schemas.analysis import Analysis
from app.services.ai_providers import GeminiProvider, demo_analysis

router = APIRouter(dependencies=[Depends(require_workspace)])


class AnalyzeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    simulated: bool = False
    consent: bool = False


def evidence_for(session, incident):
    # Raw text is used only for local classification. No raw text, names,
    # URLs, endpoints, metadata, IPs, user IDs or correlation IDs leave this API.
    rows = session.scalars(select(Log).where(
        Log.service_id == incident.service_id, Log.signature == incident.signature,
        Log.severity.in_(['ERROR', 'CRITICAL']),
        Log.received_at >= incident.first_seen, Log.received_at <= incident.last_seen)
        .order_by(Log.received_at.desc(), Log.id).limit(20)).all()
    evidence = []
    for log in rows:
        text = (log.error_type + ' ' + log.message)[:8000].lower()
        timed_out = bool(re.search(r'time[\s_-]*out|timed[\s_-]+out', text))
        category = ('database_timeout' if 'database' in text and timed_out
                    else 'payment_timeout' if ('payment' in text or 'gateway' in text) and timed_out
                    else 'timeout' if timed_out
                    else 'exception' if 'exception' in text else 'application_error')
        evidence.append({'id': str(log.id), 'severity': log.severity, 'category': category})
    return evidence


def quota(usage):
    return {'requests_remaining': max(0, settings.ai_global_daily_request_limit - usage.requests),
            'investigations_remaining': max(0, settings.ai_daily_investigation_limit - usage.investigations),
            'reset': '00:00 UTC', 'workspace': 'single-demo'}


@router.get('/ai/quota')
def get_quota(session: Session = Depends(get_session)):
    usage = session.get(AIUsage, 'single-demo')
    if not usage or usage.day != utcnow().date().isoformat():
        usage = AIUsage(requests=0, investigations=0)
    return {**quota(usage), 'external_enabled': settings.ai_external_enabled,
            'key_configured': bool(settings.gemini_api_key), 'model': settings.gemini_model}


@router.post('/incidents/{incident_id}/analysis')
def analyze(incident_id: UUID, payload: AnalyzeInput, session: Session = Depends(get_session)):
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, 'Incident not found')
    now = utcnow()
    # UPSERT + row lock serializes reservations across processes and restarts.
    session.execute(insert(AIUsage).values(workspace='single-demo', day=now.date().isoformat(),
        requests=0, investigations=0).on_conflict_do_nothing())
    usage = session.scalar(select(AIUsage).where(AIUsage.workspace == 'single-demo').with_for_update())
    now = utcnow()
    if usage.day != now.date().isoformat():
        usage.day, usage.requests, usage.investigations = now.date().isoformat(), 0, 0
    if usage.requests >= settings.ai_global_daily_request_limit:
        raise HTTPException(429, 'Daily analysis request limit reached. Monitoring remains operational; resets at 00:00 UTC.')
    if usage.last_request and now - usage.last_request < timedelta(seconds=settings.ai_request_cooldown_seconds):
        raise HTTPException(429, 'Analysis cooldown active. Wait a few seconds before retrying.')
    usage.requests += 1
    usage.last_request = now
    evidence = evidence_for(session, incident)
    fingerprint = hashlib.sha256(json.dumps([str(incident.id), str(incident.last_seen), incident.event_count,
        evidence, 'projection-v2', 'demo' if payload.simulated else settings.gemini_model], sort_keys=True).encode()).hexdigest()
    cached = session.get(AIAnalysis, fingerprint)
    def fail(code, detail):
        session.commit()  # Failed and repeated requests consume the global request budget.
        raise HTTPException(code, detail)
    if not evidence:
        fail(409, 'No matching incident evidence is available.')
    if not payload.simulated:
        if not settings.ai_external_enabled or not payload.consent:
            fail(403, 'External analysis requires operator enablement and consent to send categorical evidence to Google.')
        if not settings.gemini_api_key:
            fail(503, 'GEMINI_API_KEY is not configured. Select simulated analysis for a demo.')
    if cached and 'analysis' in cached.result:
        result = {**cached.result, 'cached': True, 'quota': quota(usage)}
        session.commit()
        return result
    if cached and now - cached.created_at < timedelta(seconds=60):
        fail(409, 'Investigation is already running or recently failed. Wait one minute before retrying.')
    if not payload.simulated:
        if usage.investigations >= settings.ai_daily_investigation_limit:
            fail(429, 'Daily AI investigation limit reached. Cached results and monitoring remain available; resets at 00:00 UTC.')
        usage.investigations += 1
    if not cached:
        cached = AIAnalysis(cache_key=fingerprint, incident_id=incident_id, result={'pending': True}, created_at=now)
        session.add(cached)
    else:
        cached.result, cached.created_at = {'pending': True}, now
    remaining = quota(usage)
    session.commit()  # Reserve quota before network IO, including timeouts/crashes.
    analysis = demo_analysis(evidence) if payload.simulated else GeminiProvider().analyze(evidence)
    analysis = Analysis.model_validate(analysis)
    ids = {e['id'] for e in evidence}
    if any(set(h.evidence_ids) - ids for h in analysis.hypotheses):
        raise HTTPException(502, 'Provider cited evidence outside this incident.')
    result = {'analysis': analysis.model_dump(), 'evidence': evidence,
              'source': 'Simulated analysis' if payload.simulated else 'Gemini',
              'model': None if payload.simulated else settings.gemini_model,
              'simulated': payload.simulated, 'generated_at': now.isoformat()}
    cached.result = result
    session.commit()
    return {**result, 'cached': False, 'quota': remaining}

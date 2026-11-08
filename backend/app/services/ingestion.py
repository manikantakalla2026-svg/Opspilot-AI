import re
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.security import digest
from app.models.entities import Incident, Log, Service, utcnow
from app.schemas.payloads import LogInput

SECRET_KEY = re.compile(r"password|secret|token|authorization|cookie|api.?key|email|card|credit", re.I)


def clean_text(value: str):
    value = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", value)
    value = re.sub(r"(?i)(password|secret|token|api[_-]?key|authorization|cookie)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", value)
    value = re.sub(r"\b(?:\d[ -]?){13,19}\b", "[REDACTED]", value)
    value = re.sub(r"(?i)(postgres(?:ql)?://)[^\s/@]+(?::[^\s/@]+)?@", r"\1[REDACTED]@", value)
    return value


def sanitize(value, depth=0):
    if depth > 5:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {clean_text(str(k))[:100]: "[REDACTED]" if SECRET_KEY.search(str(k)) else sanitize(v, depth + 1)
                for k, v in list(value.items())[:30]}
    if isinstance(value, list):
        return [sanitize(v, depth + 1) for v in value[:30]]
    return clean_text(value) if isinstance(value, str) else value


def ingest(session, service: Service, payload: LogInput):
    # Lock the service before calling this function. It serializes authentication,
    # limits, log storage, and detection across concurrent API workers.
    now = utcnow()
    recent = session.scalar(select(func.count()).select_from(Log).where(
        Log.service_id == service.id, Log.received_at >= now - timedelta(minutes=1)))
    if recent >= 120:
        raise HTTPException(429, "Service ingestion limit: 120 logs per minute")
    message = clean_text(payload.message)
    error_type = clean_text(payload.error_type)[:100]
    endpoint = clean_text(payload.endpoint.split("?")[0])[:200]
    normalized = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b\d+\b", "#", message.lower())
    signature = digest(f"{error_type.lower()}|{endpoint.lower()}|{normalized}")
    log = Log(service_id=service.id, timestamp=payload.timestamp or now,
              received_at=now, severity=payload.severity, message=message,
              error_type=error_type, endpoint=endpoint,
              correlation_id=clean_text(payload.correlation_id)[:100] if payload.correlation_id else None,
              sanitized_metadata=sanitize(payload.metadata), signature=signature)
    session.add(log)
    session.flush()
    incident = None
    if payload.severity in {"ERROR", "CRITICAL"}:
        incident = session.scalar(select(Incident).where(
            Incident.service_id == service.id, Incident.signature == signature,
            Incident.status != "Resolved"))
        if incident:
            incident.event_count += 1
            incident.last_seen = now
            if payload.severity == "CRITICAL":
                incident.severity = "CRITICAL"
        else:
            # Ignore earlier resolved events when detecting a new incident.
            last_resolved = session.scalar(select(func.max(Incident.resolved_at)).where(
                Incident.service_id == service.id, Incident.signature == signature))
            filters = [Log.service_id == service.id, Log.signature == signature,
                       Log.severity.in_(["ERROR", "CRITICAL"]),
                       Log.received_at >= now - timedelta(seconds=120)]
            if last_resolved:
                filters.append(Log.received_at > last_resolved)
            count, first, critical = session.execute(select(
                func.count(), func.min(Log.received_at),
                func.count().filter(Log.severity == "CRITICAL")).where(*filters)).one()
            if count >= 5:
                incident = Incident(service_id=service.id, signature=signature,
                                    title=(error_type or message)[:200],
                                    severity="CRITICAL" if critical else "ERROR",
                                    event_count=count, first_seen=first, last_seen=now)
                session.add(incident)
    session.flush()
    return log, incident

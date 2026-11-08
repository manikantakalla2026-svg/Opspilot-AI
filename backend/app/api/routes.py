import secrets
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import digest, require_workspace
from app.db.session import get_session
from app.models.entities import Incident, Log, Service, utcnow
from app.schemas.payloads import IncidentUpdate, LogInput, ServiceCreate, ServiceOut, ServiceUpdate, SimulationInput
from app.services.ingestion import ingest

router = APIRouter()
admin = APIRouter(dependencies=[Depends(require_workspace)])


def service_or_404(session, service_id, lock=False):
    query = select(Service).where(Service.id == service_id)
    if lock:
        query = query.with_for_update()
    service = session.scalar(query)
    if not service:
        raise HTTPException(404, "Service not found")
    return service


def service_data(service):
    return ServiceOut.model_validate(service).model_dump(mode="json")


def incident_data(incident, name):
    return {"id": incident.id, "service_id": incident.service_id, "service_name": name,
            "title": incident.title, "severity": incident.severity, "status": incident.status,
            "event_count": incident.event_count, "first_seen": incident.first_seen,
            "last_seen": incident.last_seen, "resolved_at": incident.resolved_at}


@admin.post("/services", status_code=201)
def create_service(payload: ServiceCreate, session: Session = Depends(get_session)):
    key = secrets.token_urlsafe(32)
    service = Service(**payload.model_dump(), ingestion_key_hash=digest(key))
    session.add(service)
    session.commit()
    return {**service_data(service), "ingestion_key": key}


@admin.get("/services")
def services(session: Session = Depends(get_session), limit: int = Query(50, ge=1, le=100),
             offset: int = Query(0, ge=0)):
    rows = session.scalars(select(Service).order_by(Service.created_at.desc()).limit(limit).offset(offset)).all()
    errors = dict(session.execute(select(Log.service_id, func.count()).where(
        Log.severity.in_(["ERROR", "CRITICAL"]), Log.received_at >= utcnow() - timedelta(hours=24))
        .group_by(Log.service_id)).all())
    active = dict(session.execute(select(Incident.service_id, func.count()).where(
        Incident.status != "Resolved").group_by(Incident.service_id)).all())
    return {"items": [{**service_data(s), "errors_24h": errors.get(s.id, 0),
                        "active_incidents": active.get(s.id, 0),
                        "health": "Inactive" if not s.active else "Unhealthy" if active.get(s.id) else "Healthy"}
                       for s in rows],
            "total": session.scalar(select(func.count()).select_from(Service))}


@admin.get("/services/{service_id}")
def service_detail(service_id: UUID, session: Session = Depends(get_session)):
    return service_data(service_or_404(session, service_id))


@admin.put("/services/{service_id}")
def update_service(service_id: UUID, payload: ServiceUpdate, session: Session = Depends(get_session)):
    service = service_or_404(session, service_id, lock=True)
    for field, value in payload.model_dump().items():
        setattr(service, field, value)
    session.commit()
    return service_data(service)


@admin.delete("/services/{service_id}", status_code=204)
def deactivate_service(service_id: UUID, session: Session = Depends(get_session)):
    service = service_or_404(session, service_id, lock=True)
    service.active = False
    session.commit()


@admin.post("/services/{service_id}/rotate-key")
def rotate_key(service_id: UUID, session: Session = Depends(get_session)):
    service = service_or_404(session, service_id, lock=True)
    key = secrets.token_urlsafe(32)
    service.ingestion_key_hash = digest(key)
    session.commit()
    return {"ingestion_key": key}


@router.post("/ingest/{service_id}", status_code=201)
def receive_log(service_id: UUID, payload: LogInput, x_ingestion_key: str = Header(default=""),
                session: Session = Depends(get_session)):
    service = service_or_404(session, service_id, lock=True)
    if not secrets.compare_digest(service.ingestion_key_hash, digest(x_ingestion_key)):
        raise HTTPException(401, "Invalid ingestion key")
    if not service.active:
        raise HTTPException(409, "Service is inactive")
    log, incident = ingest(session, service, payload)
    session.commit()
    return {"log_id": log.id, "incident_id": incident.id if incident else None}


@admin.get("/logs")
def logs(session: Session = Depends(get_session), service_id: UUID | None = None,
         severity: str | None = Query(None, pattern="^(INFO|WARNING|ERROR|CRITICAL)$"),
         q: str = Query("", max_length=100), since: datetime | None = None,
         until: datetime | None = None, limit: int = Query(25, ge=1, le=100),
         offset: int = Query(0, ge=0)):
    conditions = []
    if service_id:
        conditions.append(Log.service_id == service_id)
    if severity:
        conditions.append(Log.severity == severity)
    if q:
        conditions.append(Log.message.icontains(q, autoescape=True))
    if since:
        conditions.append(Log.received_at >= since)
    if until:
        conditions.append(Log.received_at <= until)
    rows = session.execute(select(Log, Service.name).join(Service).where(*conditions)
                           .order_by(Log.received_at.desc(), Log.id).limit(limit).offset(offset)).all()
    return {"items": [{"id": log.id, "service_id": log.service_id, "service_name": name,
                        "timestamp": log.timestamp, "received_at": log.received_at,
                        "severity": log.severity, "message": log.message, "error_type": log.error_type,
                        "endpoint": log.endpoint, "correlation_id": log.correlation_id,
                        "metadata": log.sanitized_metadata} for log, name in rows],
            "total": session.scalar(select(func.count()).select_from(Log).where(*conditions))}


@admin.get("/incidents/{incident_id}/evidence/{log_id}")
def incident_evidence(incident_id: UUID, log_id: UUID, session: Session = Depends(get_session)):
    incident = session.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    row = session.execute(select(Log, Service.name).join(Service).where(
        Log.id == log_id, Log.service_id == incident.service_id,
        Log.signature == incident.signature, Log.severity.in_(["ERROR", "CRITICAL"]),
        Log.received_at >= incident.first_seen, Log.received_at <= incident.last_seen)).first()
    if not row:
        raise HTTPException(404, "Evidence not found for this incident")
    log, name = row
    return {"id": log.id, "service_id": log.service_id, "service_name": name,
            "timestamp": log.timestamp, "received_at": log.received_at,
            "severity": log.severity, "message": log.message, "error_type": log.error_type,
            "endpoint": log.endpoint, "correlation_id": log.correlation_id,
            "metadata": log.sanitized_metadata}


@admin.get("/incidents")
def incidents(session: Session = Depends(get_session), service_id: UUID | None = None,
              status: str | None = Query(None, pattern="^(Open|Investigating|Resolved)$"),
              limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    conditions = []
    if service_id:
        conditions.append(Incident.service_id == service_id)
    if status:
        conditions.append(Incident.status == status)
    rows = session.execute(select(Incident, Service.name).join(Service).where(*conditions)
                           .order_by(Incident.last_seen.desc()).limit(limit).offset(offset)).all()
    return {"items": [incident_data(i, name) for i, name in rows],
            "total": session.scalar(select(func.count()).select_from(Incident).where(*conditions))}


@admin.patch("/incidents/{incident_id}")
def update_incident(incident_id: UUID, payload: IncidentUpdate, session: Session = Depends(get_session)):
    initial = session.get(Incident, incident_id)
    if not initial:
        raise HTTPException(404, "Incident not found")
    service = service_or_404(session, initial.service_id, lock=True)
    session.refresh(initial)
    # Resolving is reversible through new errors; reopening old incidents could
    # conflict with a newer active incident, so it is deliberately disallowed.
    if initial.status == "Resolved" and payload.status != "Resolved":
        raise HTTPException(409, "Resolved incidents cannot be reopened")
    if initial.status != payload.status:
        initial.status = payload.status
        initial.resolved_at = utcnow() if payload.status == "Resolved" else None
    session.commit()
    return incident_data(initial, service.name)


@admin.get("/dashboard")
def dashboard(session: Session = Depends(get_session)):
    now = utcnow()
    active_ids = select(Incident.service_id).where(Incident.status != "Resolved").distinct()
    total = session.scalar(select(func.count()).select_from(Service).where(Service.active))
    unhealthy = session.scalar(select(func.count()).select_from(Service).where(Service.active, Service.id.in_(active_ids)))
    errors = session.scalar(select(func.count()).select_from(Log).where(
        Log.severity.in_(["ERROR", "CRITICAL"]), Log.received_at >= now - timedelta(hours=24)))
    open_count = session.scalar(select(func.count()).select_from(Incident).where(Incident.status != "Resolved"))
    severity = dict(session.execute(select(Incident.severity, func.count()).where(
        Incident.status != "Resolved").group_by(Incident.severity)).all())
    hour = func.date_trunc("hour", Log.received_at)
    trend = session.execute(select(hour, func.count()).where(
        Log.received_at >= now - timedelta(hours=24), Log.severity.in_(["ERROR", "CRITICAL"]))
        .group_by(hour).order_by(hour)).all()
    return {"services": total, "healthy": total - unhealthy, "unhealthy": unhealthy,
            "errors_24h": errors, "active_incidents": open_count, "severity": severity,
            "trend": [{"time": time, "errors": count} for time, count in trend]}


@admin.post("/simulator", status_code=201)
def simulate(payload: SimulationInput, session: Session = Depends(get_session)):
    service = service_or_404(session, payload.service_id, lock=True)
    if not service.active:
        raise HTTPException(409, "Service is inactive")
    now = utcnow()
    if service.last_simulated_at and now - service.last_simulated_at < timedelta(seconds=30):
        raise HTTPException(429, "Wait 30 seconds before another simulation for this service")
    scenarios = {
        "payment_timeout": ("ERROR", "PaymentGatewayTimeout", "Payment gateway timed out after 30 seconds"),
        "database_timeout": ("ERROR", "DatabaseConnectionTimeout", "Database connection timed out after 10 seconds"),
        "exception": ("CRITICAL", "PaymentProcessingError", "Unhandled exception while processing payment"),
        "normal": ("INFO", "", "Payment completed successfully"),
    }
    severity, error_type, message = scenarios[payload.scenario]
    count = 3 if payload.scenario == "normal" else 5
    incident_id = None
    for _ in range(count):
        _, incident = ingest(session, service, LogInput(
            severity=severity, error_type=error_type, message=message,
            endpoint="/payments/checkout", metadata={"source": "quickcart_simulator", "scenario": payload.scenario}))
        if incident:
            incident_id = incident.id
    service.last_simulated_at = now
    session.commit()
    return {"logs_created": count, "incident_id": incident_id,
            "message": "Bounded QuickCart simulation completed through the ingestion pipeline"}


router.include_router(admin)

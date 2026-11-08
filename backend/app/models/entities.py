from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Service(Base):
    __tablename__ = "services"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(500), default="")
    ingestion_key_hash: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_simulated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Log(Base):
    __tablename__ = "logs"
    __table_args__ = (
        CheckConstraint("severity IN ('INFO','WARNING','ERROR','CRITICAL')", name="ck_logs_severity"),
        Index("ix_logs_detection", "service_id", "signature", "received_at"),
        Index("ix_logs_received", "received_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    severity: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    error_type: Mapped[str] = mapped_column(String(100), default="")
    endpoint: Mapped[str] = mapped_column(String(200), default="")
    correlation_id: Mapped[str | None] = mapped_column(String(100))
    sanitized_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    signature: Mapped[str] = mapped_column(String(64))


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("status IN ('Open','Investigating','Resolved')", name="ck_incidents_status"),
        CheckConstraint("severity IN ('ERROR','CRITICAL')", name="ck_incidents_severity"),
        Index("uq_incidents_active_signature", "service_id", "signature", unique=True,
              postgresql_where=text("status != 'Resolved'")),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    service_id: Mapped[UUID] = mapped_column(ForeignKey("services.id"))
    signature: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="Open")
    event_count: Mapped[int] = mapped_column(Integer, default=5)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIUsage(Base):
    __tablename__ = "ai_usage"
    workspace: Mapped[str] = mapped_column(String(30), primary_key=True)
    day: Mapped[str] = mapped_column(String(10))
    requests: Mapped[int] = mapped_column(Integer, default=0)
    investigations: Mapped[int] = mapped_column(Integer, default=0)
    last_request: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id"))
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

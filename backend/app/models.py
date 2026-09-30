from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class LogEntry(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), unique=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    service_name: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
    __table_args__ = (Index("ix_logs_service_level_time", "service_name", "level", "timestamp"),)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20))
    incident_type: Mapped[str] = mapped_column(String(40))
    service_name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")
    metric_name: Mapped[str] = mapped_column(String(80))
    metric_value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    window_seconds: Mapped[int] = mapped_column(Integer)
    metric_evidence: Mapped[dict] = mapped_column(JSON)
    log_excerpt: Mapped[list] = mapped_column(JSON)
    ai_explanation: Mapped[str | None] = mapped_column(Text)
    ai_recommendation: Mapped[list | None] = mapped_column(JSON)
    likely_cause: Mapped[str | None] = mapped_column(Text)
    uncertainty_note: Mapped[str | None] = mapped_column(Text)
    analysis_source: Mapped[str | None] = mapped_column(String(20))
    analysis_model: Mapped[str | None] = mapped_column(String(80))
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index(
            "uq_open_service_rule",
            "service_name",
            "incident_type",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )


class AnalysisAttempt(Base):
    __tablename__ = "analysis_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

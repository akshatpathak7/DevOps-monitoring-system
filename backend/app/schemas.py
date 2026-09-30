from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Level = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
FailureMode = Literal["http_errors", "latency", "error_logs", "unavailable"]
IncidentType = Literal["http_errors", "latency", "unavailable", "error_logs", "cpu", "memory"]


class LogIn(BaseModel):
    event_id: UUID
    timestamp: AwareDatetime
    service_name: str = Field(min_length=1, max_length=80)
    level: Level
    message: str = Field(min_length=1, max_length=4000)


class LogBatch(BaseModel):
    logs: list[LogIn] = Field(min_length=1, max_length=100)


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    service_name: str
    level: str
    message: str


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    severity: str
    incident_type: str
    service_name: str
    description: str
    detected_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None
    status: str
    metric_name: str
    metric_value: float
    threshold: float
    window_seconds: int
    metric_evidence: dict
    log_excerpt: list
    ai_explanation: str | None
    ai_recommendation: list[str] | None
    likely_cause: str | None
    uncertainty_note: str | None
    analysis_source: str | None
    analysis_model: str | None
    analyzed_at: datetime | None


class SimulationIn(BaseModel):
    service_name: str = "demo-service"
    mode: FailureMode
    duration_seconds: int = Field(default=60, ge=15, le=120)


class LoginIn(BaseModel):
    username: str = Field(max_length=80)
    password: str = Field(max_length=256)

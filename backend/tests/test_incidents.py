from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from sqlalchemy import func, select

from app.models import Incident
from app.services.detection_service import Detector
from app.services.prometheus_service import PrometheusError


def values(**kwargs):
    return dict(up=1, requests_window=100, error_rate=0, latency=0.02, cpu=1, memory=40, **kwargs)


async def test_create_deduplicate_resolve_recur_and_preserve_evidence(db, sessions, settings):
    prom = AsyncMock()
    prom.summary.return_value = {**values(), "error_rate": 50}
    detector = Detector(settings, sessions, prom)
    now = datetime.now(timezone.utc)
    for i in range(3):
        await detector.check_service(db, "demo-service", now + timedelta(seconds=i * 5))
    rows = (await db.scalars(select(Incident))).all()
    assert len(rows) == 1
    first = rows[0]
    assert first.metric_evidence["error_rate"] == 50
    assert first.last_seen_at == now + timedelta(seconds=10)
    prom.summary.return_value = values()
    for i in range(3):
        await detector.check_service(db, "demo-service", now + timedelta(seconds=20 + i * 5))
    assert first.status == "resolved"
    assert first.metric_value == 50
    assert first.resolved_at is not None
    prom.summary.return_value = {**values(), "error_rate": 80}
    await detector.check_service(db, "demo-service", now + timedelta(seconds=40))
    assert await db.scalar(select(func.count()).select_from(Incident)) == 2


async def test_unknown_interrupts_recovery_and_restart_preserves_open_incident(
    db, sessions, settings, incident
):
    prom = AsyncMock()
    prom.summary.return_value = values()
    detector = Detector(settings, sessions, prom)
    now = datetime.now(timezone.utc)
    for i in range(2):
        await detector.check_service(db, "demo-service", now + timedelta(seconds=i * 5))
    prom.summary.side_effect = PrometheusError("offline")
    await detector.check_service(db, "demo-service", now + timedelta(seconds=10))
    assert incident.status == "open"
    prom.summary.side_effect = None
    await detector.check_service(db, "demo-service", now + timedelta(seconds=15))
    assert incident.status == "open"
    restarted = Detector(settings, sessions, prom)
    await restarted.check_service(db, "demo-service", now + timedelta(seconds=20))
    assert incident.status == "open"
    assert await db.scalar(select(func.count()).select_from(Incident)) == 1


async def test_resource_hold_and_unknown_resets_timer(db, sessions, settings):
    prom = AsyncMock()
    prom.summary.return_value = {**values(), "cpu": 90}
    detector = Detector(settings, sessions, prom)
    now = datetime.now(timezone.utc)
    for seconds in (0, 25):
        await detector.check_service(db, "demo-service", now + timedelta(seconds=seconds))
    assert await db.scalar(select(func.count()).select_from(Incident)) == 0
    prom.summary.side_effect = PrometheusError("offline")
    await detector.check_service(db, "demo-service", now + timedelta(seconds=30))
    prom.summary.side_effect = None
    for seconds in (35, 60):
        await detector.check_service(db, "demo-service", now + timedelta(seconds=seconds))
    assert await db.scalar(select(func.count()).select_from(Incident)) == 0
    await detector.check_service(db, "demo-service", now + timedelta(seconds=65))
    assert (await db.scalar(select(Incident))).incident_type == "cpu"


async def test_unavailable_startup_grace(db, sessions, settings):
    prom = AsyncMock()
    prom.summary.return_value = {"up": None}
    detector = Detector(settings, sessions, prom)
    now = detector.started
    for seconds in (0, 25, 30, 45):
        await detector.check_service(db, "demo-service", now + timedelta(seconds=seconds))
    assert await db.scalar(select(func.count()).select_from(Incident)) == 0
    await detector.check_service(db, "demo-service", now + timedelta(seconds=50))
    assert (await db.scalar(select(Incident))).severity == "critical"


async def test_database_rejects_two_open_incidents_for_same_rule(db, incident):
    import pytest
    from sqlalchemy.exc import IntegrityError

    duplicate = Incident(
        title=incident.title,
        severity=incident.severity,
        incident_type=incident.incident_type,
        service_name=incident.service_name,
        description=incident.description,
        detected_at=incident.detected_at,
        last_seen_at=incident.last_seen_at,
        status="open",
        metric_name=incident.metric_name,
        metric_value=20,
        threshold=10,
        window_seconds=60,
        metric_evidence={},
        log_excerpt=[],
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()

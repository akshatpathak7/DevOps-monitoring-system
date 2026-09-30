import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from ..models import AnalysisAttempt, Incident, LogEntry
from ..rules.detection_rules import evaluate
from .log_service import evidence_logs
from .prometheus_service import PrometheusError

logger = logging.getLogger(__name__)


class Detector:
    def __init__(self, settings, sessions, prometheus):
        self.settings, self.sessions, self.prometheus = settings, sessions, prometheus
        self.started = datetime.now(timezone.utc)
        self.pending = {}
        self.healthy = {}
        self.last_cleanup = self.started - timedelta(hours=1)

    async def check_service(self, db, service, now):
        try:
            metrics = await self.prometheus.summary(service)
        except PrometheusError:
            metrics = None
        errors = await db.scalar(
            select(func.count())
            .select_from(LogEntry)
            .where(
                LogEntry.service_name == service,
                LogEntry.level == "ERROR",
                LogEntry.timestamp >= now - timedelta(seconds=60),
                LogEntry.timestamp <= now,
            )
        )
        for result in evaluate(metrics, errors, self.settings):
            key = (service, result.kind)
            if (
                result.kind == "unavailable"
                and (now - self.started).total_seconds() < self.settings.startup_grace
            ):
                continue
            if result.breached is None:
                self.pending.pop(key, None)
                self.healthy.pop(key, None)
                continue
            incident = await db.scalar(
                select(Incident).where(
                    Incident.service_name == service,
                    Incident.incident_type == result.kind,
                    Incident.status == "open",
                )
            )
            if result.breached:
                self.healthy.pop(key, None)
                first = self.pending.setdefault(key, now)
                if incident:
                    incident.last_seen_at = now
                elif (now - first).total_seconds() >= result.hold_seconds:
                    logs = await evidence_logs(db, service, now)
                    evidence = {**(metrics or {}), "error_logs": errors}
                    await db.execute(
                        insert(Incident)
                        .values(
                            title=result.title,
                            severity="critical" if result.kind == "unavailable" else "warning",
                            incident_type=result.kind,
                            service_name=service,
                            description=f"{result.title} on {service}; observed {result.value:.2f}, threshold {result.threshold:g}.",
                            detected_at=now,
                            last_seen_at=now,
                            status="open",
                            metric_name=result.metric,
                            metric_value=result.value,
                            threshold=result.threshold,
                            window_seconds=result.window,
                            metric_evidence=evidence,
                            log_excerpt=logs,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[Incident.service_name, Incident.incident_type],
                            index_where=Incident.status == "open",
                        )
                    )
            else:
                self.pending.pop(key, None)
                if incident:
                    self.healthy[key] = self.healthy.get(key, 0) + 1
                    if self.healthy[key] >= 3:
                        incident.status = "resolved"
                        incident.resolved_at = now
                        self.healthy.pop(key, None)
                else:
                    self.healthy.pop(key, None)
        await db.commit()

    async def tick(self):
        now = datetime.now(timezone.utc)
        for service in self.settings.service_urls:
            async with self.sessions() as db:
                await self.check_service(db, service, now)
        if now - self.last_cleanup >= timedelta(hours=1):
            async with self.sessions() as db:
                await db.execute(delete(LogEntry).where(LogEntry.timestamp < now - timedelta(days=7)))
                await db.execute(
                    delete(AnalysisAttempt).where(AnalysisAttempt.attempted_at < now - timedelta(days=1))
                )
                await db.commit()
            self.last_cleanup = now

    async def run(self):
        while True:
            try:
                await self.tick()
            except Exception:
                logger.exception("Detection pass failed; retrying on the next interval")
            await asyncio.sleep(self.settings.detection_interval)

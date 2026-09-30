import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from ..models import LogEntry


def redact(message: str) -> str:
    message = re.sub(r"(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[^\s,;]+", r"\1[REDACTED]", message)
    message = re.sub(
        r"(?i)((?:api[_-]?key|password|token|secret)\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", message
    )
    return re.sub(r"\bsk-[A-Za-z0-9_-]{12,}", "[REDACTED]", message)


async def ingest(db, logs):
    now = datetime.now(timezone.utc)
    if any(
        log.timestamp > now + timedelta(minutes=1) or log.timestamp < now - timedelta(days=7) for log in logs
    ):
        raise HTTPException(
            422, "Log timestamps must be within retention and at most one minute in the future"
        )
    rows = [
        {**log.model_dump(), "event_id": str(log.event_id), "message": redact(log.message)} for log in logs
    ]
    result = await db.execute(
        insert(LogEntry)
        .values(rows)
        .on_conflict_do_nothing(index_elements=[LogEntry.event_id])
        .returning(LogEntry.id)
    )
    inserted = len(result.all())
    await db.commit()
    return inserted


async def evidence_logs(db, service, now):
    rows = (
        await db.scalars(
            select(LogEntry)
            .where(
                LogEntry.service_name == service,
                LogEntry.timestamp >= now - timedelta(minutes=2),
                LogEntry.timestamp <= now,
            )
            .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
            .limit(30)
        )
    ).all()
    return [
        {
            "timestamp": row.timestamp.isoformat(),
            "level": row.level,
            "message": row.message[:1000],
            "service_name": row.service_name,
        }
        for row in rows
    ]

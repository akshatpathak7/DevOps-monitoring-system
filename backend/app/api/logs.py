from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from ..database import get_db
from ..models import LogEntry
from ..schemas import Level, LogBatch, LogOut
from ..security import require_ingest
from ..services.log_service import ingest
from .common import validate_service

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.post("", dependencies=[Depends(require_ingest)])
async def receive(body: LogBatch, db=Depends(get_db)):
    for log in body.logs:
        validate_service(log.service_name)
    return {"inserted": await ingest(db, body.logs)}


@router.get("")
async def logs(
    service_name: str | None = None,
    level: Level | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    db=Depends(get_db),
):
    validate_service(service_name)
    if (since and not since.tzinfo) or (until and not until.tzinfo):
        raise HTTPException(422, "Time filters require a timezone")
    if since and until and since > until:
        raise HTTPException(422, "since must precede until")
    conditions = []
    if service_name:
        conditions.append(LogEntry.service_name == service_name)
    if level:
        conditions.append(LogEntry.level == level)
    if since:
        conditions.append(LogEntry.timestamp >= since)
    if until:
        conditions.append(LogEntry.timestamp <= until)
    total = await db.scalar(select(func.count()).select_from(LogEntry).where(*conditions))
    rows = (
        await db.scalars(
            select(LogEntry)
            .where(*conditions)
            .order_by(LogEntry.timestamp.desc(), LogEntry.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return {"items": [LogOut.model_validate(row) for row in rows], "total": total}

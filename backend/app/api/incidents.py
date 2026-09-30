from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from ..database import get_db
from ..models import Incident
from ..schemas import IncidentOut, IncidentType
from .common import validate_service

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


async def find_incident(db, incident_id):
    row = await db.get(Incident, incident_id)
    if not row:
        raise HTTPException(404, "Incident not found")
    return row


@router.get("")
async def incidents(
    service_name: str | None = None,
    status: Literal["open", "resolved"] | None = None,
    incident_type: IncidentType | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=100000),
    db=Depends(get_db),
):
    validate_service(service_name)
    conditions = []
    for field, value in [
        (Incident.service_name, service_name),
        (Incident.status, status),
        (Incident.incident_type, incident_type),
    ]:
        if value is not None:
            conditions.append(field == value)
    total = await db.scalar(select(func.count()).select_from(Incident).where(*conditions))
    rows = (
        await db.scalars(
            select(Incident)
            .where(*conditions)
            .order_by(Incident.detected_at.desc(), Incident.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {"items": [IncidentOut.model_validate(row) for row in rows], "total": total}


@router.get("/{incident_id}", response_model=IncidentOut)
async def detail(incident_id: int, db=Depends(get_db)):
    return await find_incident(db, incident_id)

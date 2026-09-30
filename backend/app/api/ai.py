from fastapi import APIRouter, Depends, Request

from ..database import get_db
from ..schemas import IncidentOut
from ..security import require_admin
from .incidents import find_incident

router = APIRouter(tags=["AI troubleshooting"])


@router.post(
    "/api/incidents/{incident_id}/analyze", response_model=IncidentOut, dependencies=[Depends(require_admin)]
)
async def analyze(incident_id: int, request: Request, db=Depends(get_db)):
    incident = await find_incident(db, incident_id)
    return await request.app.state.ai.analyze(db, incident)

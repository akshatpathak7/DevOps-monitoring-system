import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from ..config import get_settings
from ..schemas import SimulationIn
from ..security import require_admin
from .common import validate_service

router = APIRouter(prefix="/api/demo", tags=["demo"])


async def control(request, service, path, payload=None):
    validate_service(service)
    settings = get_settings()
    url = settings.service_urls[service] + path
    try:
        response = await request.app.state.http.request(
            "POST" if payload else "GET",
            url,
            json=payload,
            headers={"Authorization": f"Bearer {settings.demo_control_token}"},
        )
        if response.status_code == 409:
            raise HTTPException(409, "This service already has an active simulation")
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Demo control unavailable; retry shortly") from exc


@router.get("/status")
async def status(request: Request, service_name: str = "demo-service"):
    return await control(request, service_name, "/control/status")


@router.post("/simulate-failure", dependencies=[Depends(require_admin)])
async def simulate(body: SimulationIn, request: Request):
    return await control(request, body.service_name, "/control/simulate", body.model_dump())

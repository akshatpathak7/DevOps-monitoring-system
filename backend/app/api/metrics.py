import asyncio
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select

from ..config import get_settings
from ..database import get_db
from ..models import Incident
from ..services.prometheus_service import METRICS, PrometheusError
from .common import validate_service

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary")
async def summary(request: Request, service_name: str | None = None, db=Depends(get_db)):
    validate_service(service_name)
    names = [service_name] if service_name else list(get_settings().service_urls)

    async def collect(name):
        try:
            values = await request.app.state.prometheus.summary(name)
            status = "healthy" if values["up"] == 1 else "unavailable"
            if status == "unavailable":
                values = {key: (values[key] if key == "up" else None) for key in METRICS}
            return {"service_name": name, "status": status, "metrics": values}
        except PrometheusError:
            return {"service_name": name, "status": "unknown", "metrics": dict.fromkeys(METRICS)}

    services = await asyncio.gather(*(collect(name) for name in names))
    counts = dict(
        (
            await db.execute(
                select(Incident.service_name, func.count())
                .where(Incident.status == "open")
                .group_by(Incident.service_name)
            )
        ).all()
    )
    for service in services:
        service["open_incidents"] = counts.get(service["service_name"], 0)
        if service["status"] == "healthy" and service["open_incidents"]:
            service["status"] = "degraded"
    return {"services": services, "updated_at": datetime.now(timezone.utc).isoformat()}


@router.get("/history")
async def history(
    request: Request,
    service_name: str = "demo-service",
    metric: Literal["request_count", "error_rate", "latency", "uptime", "cpu", "memory", "up"] = "error_rate",
    minutes: int = Query(15, ge=1, le=1440),
):
    validate_service(service_name)
    try:
        points = await request.app.state.prometheus.history(service_name, metric, minutes)
        return {"service_name": service_name, "metric": metric, "points": points}
    except PrometheusError:
        raise HTTPException(503, "Prometheus unavailable; retry shortly")

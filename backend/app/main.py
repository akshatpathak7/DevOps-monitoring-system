import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api import ai, auth, demo, incidents, logs, metrics
from .config import get_settings
from .database import Session, engine
from .services.ai_service import AIService
from .services.detection_service import Detector
from .services.prometheus_service import PrometheusService

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app):
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5, limits=httpx.Limits(max_connections=30)) as client:
        app.state.http = client
        app.state.prometheus = PrometheusService(client, settings.prometheus_url)
        app.state.ai = AIService(settings)
        detector = Detector(settings, Session, app.state.prometheus)
        task = asyncio.create_task(detector.run()) if settings.enable_detection else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            await app.state.ai.close()
            await engine.dispose()


app = FastAPI(title="DevOps monitoring system", version="0.1.0", lifespan=lifespan)
for router in (auth.router, metrics.router, logs.router, incidents.router, ai.router, demo.router):
    app.include_router(router)


@app.middleware("http")
async def limit_and_headers(request: Request, call_next):
    # The public proxy enforces the same limit; this also bounds internal chunked ingestion.
    if request.method in {"POST", "PUT", "PATCH"}:
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 512_000:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/health")
async def health():
    try:
        async with Session() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)

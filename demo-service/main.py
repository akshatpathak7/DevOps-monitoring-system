import asyncio
from collections import deque
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
import hmac
import logging
import os
import time
from typing import Literal
from uuid import uuid4
import httpx
import psutil
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo")
SERVICE = os.getenv("SERVICE_NAME", "demo-service")
BACKEND = os.getenv("BACKEND_URL", "http://backend:8000")
INGEST_TOKEN = os.environ["INGEST_TOKEN"]
CONTROL_TOKEN = os.environ["DEMO_CONTROL_TOKEN"]
PORT = int(os.getenv("PORT", "8001"))
registry = CollectorRegistry()
requests = Counter(
    "demo_requests_total",
    "Application requests by HTTP status",
    ["status"],
    registry=registry,
)
for code in ("200", "500"):
    requests.labels(status=code).inc(0)
latency = Histogram(
    "demo_request_duration_seconds",
    "Application response latency",
    registry=registry,
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5),
)
start_time = Gauge(
    "process_start_time_seconds", "Process start Unix time", registry=registry
)
start_time.set(time.time())
cpu = Gauge(
    "process_cpu_seconds_total",
    "Cumulative user and system CPU seconds",
    registry=registry,
)
memory = Gauge(
    "process_resident_memory_bytes", "Resident process memory", registry=registry
)
process = psutil.Process()
queue = deque(maxlen=1000)
dropped = Counter(
    "demo_logs_dropped_total",
    "Logs discarded when the delivery queue is full",
    registry=registry,
)
active_mode = None
expires_monotonic = 0.0
expires_at = None


def emit(level, message):
    if len(queue) == queue.maxlen:
        dropped.inc()
    queue.append(
        {
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "service_name": SERVICE,
            "level": level,
            "message": message,
        }
    )


def current_mode():
    global active_mode
    if active_mode and time.monotonic() >= expires_monotonic:
        emit("INFO", f"Simulation {active_mode} expired; normal behavior restored")
        active_mode = None
    return active_mode


def require_control(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, f"Bearer {CONTROL_TOKEN}"):
        raise HTTPException(401, "Invalid control credential")


async def deliver(client):
    batch = []
    delay = 1
    while True:
        if not batch:
            batch = [queue.popleft() for _ in range(min(100, len(queue)))]
        if batch:
            try:
                response = await client.post(
                    BACKEND + "/api/logs",
                    json={"logs": batch},
                    headers={"Authorization": f"Bearer {INGEST_TOKEN}"},
                )
                response.raise_for_status()
                batch = []
                delay = 1
            except httpx.HTTPError:
                logger.warning("Log delivery failed; bounded batch will be retried")
                # Discard batches older than retention so delivery can recover after a long outage.
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                batch = [
                    row
                    for row in batch
                    if datetime.fromisoformat(row["timestamp"]) >= cutoff
                ]
                delay = min(delay * 2, 15)
        await asyncio.sleep(delay)


async def generate_traffic(client):
    pending = set()

    async def hit():
        try:
            await client.get(f"http://127.0.0.1:{PORT}/work")
        except httpx.HTTPError:
            pass

    try:
        while True:
            current_mode()
            if len(pending) < 8:
                task = asyncio.create_task(hit())
                pending.add(task)
                task.add_done_callback(pending.discard)
            await asyncio.sleep(0.5)
    finally:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=5) as client:
        tasks = [
            asyncio.create_task(deliver(client)),
            asyncio.create_task(generate_traffic(client)),
        ]
        emit("INFO", "Demo service started; synthetic traffic enabled")
        yield
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/work")
async def work():
    started = time.monotonic()
    mode = current_mode()
    await asyncio.sleep(1.5 if mode == "latency" else 0.02)
    status = 500 if mode == "http_errors" else 200
    if status == 500:
        emit("ERROR", "GET /work returned 500: simulated downstream dependency failure")
    elif mode == "error_logs":
        emit(
            "ERROR",
            "Simulated background operation failed; request completed using fallback",
        )
    else:
        emit("INFO", f"GET /work returned 200 in {time.monotonic() - started:.3f}s")
    requests.labels(status=str(status)).inc()
    latency.observe(time.monotonic() - started)
    return JSONResponse(
        {"service": SERVICE, "status": "error" if status == 500 else "ok"},
        status_code=status,
    )


@app.get("/metrics")
async def metrics():
    if current_mode() == "unavailable":
        return Response("Simulated metrics outage", status_code=503)
    times = process.cpu_times()
    cpu.set(times.user + times.system)
    memory.set(process.memory_info().rss)
    return Response(
        generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST}
    )


class Simulation(BaseModel):
    service_name: str = SERVICE
    mode: Literal["http_errors", "latency", "error_logs", "unavailable"]
    duration_seconds: int = Field(default=60, ge=15, le=120)


@app.get("/control/status", dependencies=[Depends(require_control)])
async def status():
    mode = current_mode()
    return {
        "service_name": SERVICE,
        "mode": mode,
        "expires_at": expires_at if mode else None,
    }


@app.post("/control/simulate", dependencies=[Depends(require_control)])
async def simulate(body: Simulation):
    global active_mode, expires_at, expires_monotonic
    if body.service_name != SERVICE:
        raise HTTPException(422, "Unknown service")
    if current_mode():
        raise HTTPException(409, "A simulation is already active")
    active_mode = body.mode
    expires_monotonic = time.monotonic() + body.duration_seconds
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=body.duration_seconds)
    ).isoformat()
    emit(
        "WARNING",
        f"Starting bounded simulation: {body.mode} for {body.duration_seconds}s",
    )
    return await status()

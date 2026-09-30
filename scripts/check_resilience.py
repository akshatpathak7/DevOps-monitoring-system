"""Verify outage handling and persistence on the running local Compose demo.

This intentionally stops Prometheus briefly and restarts the backend.
It always attempts to start Prometheus again, including on assertion failure.
"""

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "http://localhost:8080"


def get(path):
    with urllib.request.urlopen(ORIGIN + "/api" + path, timeout=10) as response:
        return json.load(response)


def wait_until(check, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (urllib.error.URLError, ConnectionError):
            pass
        time.sleep(1)
    raise AssertionError("Timed out waiting for local service readiness")


def compose(*args):
    subprocess.run(["docker", "compose", *args], cwd=ROOT, check=True, timeout=45)


wait_until(lambda: get("/incidents?status=open")["total"] == 0, 150)
before = {row["id"]: row for row in get("/incidents?limit=100")["items"]}
assert before, "Run a failure simulation first to create persistence evidence"
try:
    compose("stop", "prometheus")
    wait_until(
        lambda: all(
            s["status"] == "unknown" for s in get("/metrics/summary")["services"]
        )
    )
    # Observe longer than the unavailable rule hold: an upstream monitoring outage
    # must not be mistaken for an application outage.
    end = time.monotonic() + 25
    while time.monotonic() < end:
        summary = get("/metrics/summary")
        assert all(s["status"] == "unknown" for s in summary["services"])
        assert all(
            all(v is None for v in s["metrics"].values()) for s in summary["services"]
        )
        time.sleep(2)
    assert get("/incidents?status=open")["total"] == 0
    print(
        "PASS Prometheus outage stays unknown and creates no false service incidents",
        flush=True,
    )
finally:
    compose("start", "prometheus")
wait_until(
    lambda: all(s["status"] == "healthy" for s in get("/metrics/summary")["services"])
)
compose("restart", "backend")
wait_until(lambda: get("/health")["status"] == "ok")
after = {row["id"]: row for row in get("/incidents?limit=100")["items"]}
for incident_id, row in before.items():
    assert after[incident_id] == row, f"Incident {incident_id} changed across restart"
print(
    "PASS backend restart preserved incidents, log snapshots, and saved AI explanations",
    flush=True,
)

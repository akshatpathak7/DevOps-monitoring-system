"""Exercise each non-HTTP simulation against a running LOCAL demo stack."""

import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.request

ORIGIN = "http://localhost:8080"
client = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)
headers = {"Content-Type": "application/json", "Origin": ORIGIN}


def request(path, body=None):
    payload = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(ORIGIN + "/api" + path, data=payload, headers=headers)
    with client.open(req, timeout=10) as response:
        return json.load(response)


def wait_until(check, description, timeout=100):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            value = check()
            if value:
                return value
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise
        except urllib.error.URLError:
            pass  # A short restart may interrupt an otherwise valid polling check.
        time.sleep(2)
    raise AssertionError("Timed out: " + description)


session = request(
    "/auth/login",
    {"username": "admin", "password": os.getenv("ADMIN_PASSWORD", "ThemistoDemo2026!")},
)
headers["X-CSRF-Token"] = session["csrf"]
wait_until(
    lambda: request("/incidents?status=open")["total"] == 0,
    "previous incidents recover",
    150,
)
for mode in ("latency", "error_logs", "unavailable"):
    before = {row["id"] for row in request("/incidents")["items"]}
    result = request("/demo/simulate-failure", {"mode": mode, "duration_seconds": 40})
    assert result["mode"] == mode
    try:
        request("/demo/simulate-failure", {"mode": mode})
        raise AssertionError("Overlapping simulation was accepted")
    except urllib.error.HTTPError as exc:
        assert exc.code == 409
    incident = wait_until(
        lambda: next(
            (
                row
                for row in request("/incidents")["items"]
                if row["id"] not in before and row["incident_type"] == mode
            ),
            None,
        ),
        mode + " incident",
        90,
    )
    print(f"PASS {mode}: real telemetry created incident #{incident['id']}", flush=True)
    if mode == "unavailable":
        assert request("/metrics/summary")["services"][0]["status"] == "unavailable"
    wait_until(lambda: request("/demo/status")["mode"] is None, mode + " expiry", 50)
    print(f"PASS {mode}: simulation expired automatically", flush=True)
wait_until(
    lambda: request("/incidents?status=open")["total"] == 0,
    "all incidents recover",
    150,
)
request("/auth/logout", {})
print("PASS all simulations recovered; no open incidents remain", flush=True)

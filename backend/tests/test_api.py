from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from app.config import get_settings
from app.main import app
from app.security import COOKIE_NAME, serializer
from app.services.prometheus_service import PrometheusError


def log(level="INFO", **kwargs):
    return {
        "event_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service_name": "demo-service",
        "level": level,
        "message": "synthetic event",
        **kwargs,
    }


async def test_ingestion_deduplication_filtering_and_validation(client):
    headers = {"Authorization": "Bearer " + get_settings().ingest_token}
    event = log("ERROR", message="password=secret token=hidden")
    response = await client.post("/api/logs", json={"logs": [event, log()]}, headers=headers)
    assert response.json()["inserted"] == 2
    assert (await client.post("/api/logs", json={"logs": [event]}, headers=headers)).json()["inserted"] == 0
    rows = (await client.get("/api/logs?level=ERROR&service_name=demo-service")).json()
    assert rows["total"] == 1
    assert "secret" not in rows["items"][0]["message"]
    assert "hidden" not in rows["items"][0]["message"]
    assert (await client.get("/api/logs?service_name=unknown")).status_code == 422
    assert (await client.get("/api/logs?limit=1000")).status_code == 422
    assert (await client.get("/api/logs?since=2026-01-01T00:00:00")).status_code == 422
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    assert (
        await client.post("/api/logs", json={"logs": [log(timestamp=future)]}, headers=headers)
    ).status_code == 422


async def test_anonymous_reads_and_mutation_protection(client, incident):
    for path in (
        "/api/health",
        "/api/logs",
        "/api/incidents",
        f"/api/incidents/{incident.id}",
        "/api/auth/me",
    ):
        assert (await client.get(path)).status_code == 200
    assert (await client.post("/api/logs", json={"logs": [log()]})).status_code == 401
    assert (await client.post(f"/api/incidents/{incident.id}/analyze")).status_code == 401
    assert (await client.post("/api/demo/simulate-failure", json={"mode": "http_errors"})).status_code == 401
    assert (await client.get("/api/incidents/999999")).status_code == 404


async def test_login_csrf_and_logout(client, admin, incident):
    path = f"/api/incidents/{incident.id}/analyze"
    assert (await client.post(path)).status_code == 403
    assert (await client.post(path, headers={**admin, "Origin": "https://evil.example"})).status_code == 403
    response = await client.post(path, headers=admin)
    assert response.status_code == 200
    assert response.json()["analysis_source"] == "demo"
    again = await client.post(path, headers=admin)
    assert again.json()["analyzed_at"] == response.json()["analyzed_at"]
    assert (await client.post("/api/auth/logout", headers=admin)).status_code == 200
    assert not (await client.get("/api/auth/me")).json()["authenticated"]


async def test_expired_cookie(client):
    with patch("itsdangerous.timed.TimestampSigner.get_timestamp", return_value=1):
        token = serializer().dumps({"username": "admin", "csrf": "x"})
    client.cookies.set(COOKIE_NAME, token)
    assert not (await client.get("/api/auth/me")).json()["authenticated"]


async def test_login_throttling_and_origin(client):
    body = {"username": "admin", "password": "wrong"}
    assert (await client.post("/api/auth/login", json=body)).status_code == 403
    for _ in range(5):
        assert (
            await client.post("/api/auth/login", json=body, headers={"Origin": "http://localhost:8080"})
        ).status_code == 401
    assert (
        await client.post("/api/auth/login", json=body, headers={"Origin": "http://localhost:8080"})
    ).status_code == 429


async def test_prometheus_unavailable_is_unknown(client):
    app.state.prometheus.summary = AsyncMock(side_effect=PrometheusError("offline"))
    response = await client.get("/api/metrics/summary")
    service = response.json()["services"][0]
    assert service["status"] == "unknown"
    assert all(value is None for value in service["metrics"].values())
    assert (await client.get("/api/metrics/history?metric=arbitrary_promql")).status_code == 422


async def test_simulation_validation(client, admin):
    assert (
        await client.post(
            "/api/demo/simulate-failure", headers=admin, json={"mode": "http_errors", "duration_seconds": 121}
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/demo/simulate-failure",
            headers=admin,
            json={"mode": "http_errors", "service_name": "unknown"},
        )
    ).status_code == 422


async def test_body_limit(client):
    assert (await client.post("/api/logs", content=b"x" * 512001)).status_code == 413


async def test_time_filters_and_pagination(client):
    headers = {"Authorization": "Bearer " + get_settings().ingest_token}
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=1)).isoformat()
    await client.post("/api/logs", json={"logs": [log(timestamp=old), log(), log()]}, headers=headers)
    result = await client.get(
        "/api/logs", params={"since": (now - timedelta(minutes=1)).isoformat(), "limit": 1}
    )
    assert result.json()["total"] == 2
    assert len(result.json()["items"]) == 1
    result = await client.get("/api/logs", params={"until": (now - timedelta(minutes=1)).isoformat()})
    assert result.json()["total"] == 1
    assert (await client.get("/api/logs", params={"since": now.isoformat(), "until": old})).status_code == 422


async def test_session_cookie_flags(client):
    response = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "TestPassword123!"},
        headers={"Origin": "http://localhost:8080"},
    )
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert "max-age=3600" in cookie


async def test_reachable_service_with_incident_is_degraded(client, incident):
    app.state.prometheus.summary = AsyncMock(return_value={"up": 1, "error_rate": 50})
    response = await client.get("/api/metrics/summary")
    service = response.json()["services"][0]
    assert service["status"] == "degraded"
    assert service["open_incidents"] == 1

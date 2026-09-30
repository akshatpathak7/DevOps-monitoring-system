import httpx
import pytest

from app.services.prometheus_service import PrometheusError, PrometheusService, parse_response, queries


def payload(kind, rows):
    return {"status": "success", "data": {"resultType": kind, "result": rows}}


@pytest.mark.parametrize(
    "value,expected", [("12.5", 12.5), ("0", 0), ("NaN", None), ("+Inf", None), ("bad", None)]
)
def test_parse_vector(value, expected):
    assert parse_response(payload("vector", [{"value": [100, value]}]), "vector") == expected


def test_empty_vector_and_matrix():
    assert parse_response(payload("vector", []), "vector") is None
    assert parse_response(payload("matrix", []), "matrix") == []


def test_matrix_preserves_gaps():
    rows = parse_response(payload("matrix", [{"values": [[100, "2"], [105, "NaN"]]}]), "matrix")
    assert rows[0]["value"] == 2
    assert rows[1]["value"] is None
    assert rows[0]["timestamp"].endswith("+00:00")


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"status": "error"},
        payload("scalar", []),
        payload("vector", [{}]),
        payload("vector", [{"value": [1, "1"]}] * 2),
    ],
)
def test_malformed(value):
    with pytest.raises(PrometheusError):
        parse_response(value, "vector")


async def test_network_error():
    async def fail(request):
        raise httpx.ConnectError("offline")

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(PrometheusError):
            await PrometheusService(client, "http://prom").summary("demo-service")


def test_service_label_is_quoted():
    assert 'service="demo-service"' in queries("demo-service")["up"]


async def test_history_fills_missing_scrape_intervals():
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock, patch

    service = PrometheusService(None, "http://prom")
    service.query = AsyncMock(
        return_value=[
            {"timestamp": datetime.fromtimestamp(940, timezone.utc).isoformat(), "value": 12},
            {"timestamp": datetime.fromtimestamp(950, timezone.utc).isoformat(), "value": 13},
        ]
    )
    with patch("app.services.prometheus_service.time.time", return_value=1000):
        points = await service.history("demo-service", "memory", 1)
    assert len(points) == 13
    assert [p["value"] for p in points[:3]] == [12, None, 13]
    assert "and on()" in service.query.call_args.args[0]

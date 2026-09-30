import asyncio
import json
import math
import time
from datetime import datetime, timezone

import httpx

METRICS = ("request_count", "requests_window", "error_rate", "latency", "uptime", "cpu", "memory", "up")


class PrometheusError(Exception):
    pass


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def parse_response(payload: dict, expected: str):
    try:
        if payload["status"] != "success" or payload["data"]["resultType"] != expected:
            raise PrometheusError("Unexpected Prometheus response")
        result = payload["data"]["result"]
        if not isinstance(result, list) or len(result) > 1:
            raise PrometheusError("Expected a single aggregated metric series")
        if not result:
            return None if expected == "vector" else []
        if expected == "vector":
            sample = result[0]["value"]
            return finite(sample[1])
        return [
            {"timestamp": datetime.fromtimestamp(float(t), timezone.utc).isoformat(), "value": finite(v)}
            for t, v in result[0]["values"]
        ]
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise PrometheusError("Malformed Prometheus response") from exc


def queries(service):
    label = f"service={json.dumps(service)}"
    requests = f"demo_requests_total{{{label}}}"
    errors = f'demo_requests_total{{{label},status=~"5.."}}'
    return {
        "request_count": f"sum({requests})",
        "requests_window": f"sum(increase({requests}[1m]))",
        "error_rate": f"100 * sum(rate({errors}[1m])) / sum(rate({requests}[1m]))",
        "latency": f"histogram_quantile(0.95, sum by (le) (rate(demo_request_duration_seconds_bucket{{{label}}}[1m])))",
        "uptime": f"time() - max(process_start_time_seconds{{{label}}})",
        "cpu": f"100 * sum(rate(process_cpu_seconds_total{{{label}}}[1m]))",
        "memory": f"sum(process_resident_memory_bytes{{{label}}}) / 1024 / 1024",
        "up": f"min(up{{{label}}} and (time() - timestamp(up{{{label}}}) < 15))",
    }


class PrometheusService:
    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self.client = client
        self.base_url = base_url.rstrip("/")

    async def query(self, expression, start=None, end=None, step=5):
        path = "/api/v1/query" if start is None else "/api/v1/query_range"
        params = {"query": expression}
        if start is not None:
            params.update(start=start, end=end, step=step)
        try:
            response = await self.client.get(self.base_url + path, params=params)
            response.raise_for_status()
            return parse_response(response.json(), "vector" if start is None else "matrix")
        except (httpx.HTTPError, ValueError) as exc:
            raise PrometheusError("Prometheus is unavailable") from exc

    async def summary(self, service):
        expressions = queries(service)
        results = await asyncio.gather(*(self.query(q) for q in expressions.values()))
        return dict(zip(expressions, results))

    async def history(self, service, metric, minutes):
        step = max(5, minutes)
        end = int(time.time())
        start = end - minutes * 60
        # Missing/failed scrapes are chart gaps, rather than stale healthy values.
        expression = queries(service)[metric]
        if metric != "up":
            expression = f"({expression}) and on() ({queries(service)['up']} == 1)"
        points = await self.query(expression, start, end, step)
        by_timestamp = {int(datetime.fromisoformat(p["timestamp"]).timestamp()): p["value"] for p in points}
        return [
            {
                "timestamp": datetime.fromtimestamp(stamp, timezone.utc).isoformat(),
                "value": by_timestamp.get(stamp),
            }
            for stamp in range(start, end + 1, step)
        ]

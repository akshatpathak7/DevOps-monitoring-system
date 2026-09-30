from dataclasses import dataclass


@dataclass(frozen=True)
class RuleResult:
    kind: str
    title: str
    metric: str
    value: float | None
    threshold: float
    window: int
    breached: bool | None
    hold_seconds: float = 0


def evaluate(metrics: dict | None, error_logs: int, settings):
    def metric_rule(kind, title, metric, threshold, window=60, hold=0, min_traffic=False):
        value = metrics.get(metric) if metrics else None
        known = metrics is not None and metrics.get("up") == 1 and value is not None
        if min_traffic:
            traffic = metrics.get("requests_window") if metrics else None
            known = known and traffic is not None and traffic >= settings.min_requests
        return RuleResult(
            kind, title, metric, value, threshold, window, value > threshold if known else None, hold
        )

    up = metrics.get("up") if metrics else None
    results = [
        metric_rule(
            "http_errors", "Elevated HTTP errors", "error_rate", settings.error_threshold, min_traffic=True
        ),
        metric_rule(
            "latency", "Slow application responses", "latency", settings.latency_threshold, min_traffic=True
        ),
        RuleResult(
            "unavailable",
            "Service metrics unavailable",
            "up",
            up if up is not None else 0,
            1,
            int(settings.unavailable_seconds),
            up != 1 if metrics is not None else None,
            settings.unavailable_seconds,
        ),
        RuleResult(
            "error_logs",
            "Repeated application errors",
            "error_logs",
            error_logs,
            settings.error_log_threshold,
            60,
            error_logs >= settings.error_log_threshold,
        ),
        metric_rule(
            "cpu",
            "High process CPU usage",
            "cpu",
            settings.cpu_threshold,
            window=int(settings.resource_seconds),
            hold=settings.resource_seconds,
        ),
        metric_rule(
            "memory",
            "High process memory usage",
            "memory",
            settings.memory_threshold,
            window=int(settings.resource_seconds),
            hold=settings.resource_seconds,
        ),
    ]
    return results

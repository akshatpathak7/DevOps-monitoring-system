import pytest

from app.rules.detection_rules import evaluate


def metrics(**extra):
    return {
        "up": 1,
        "requests_window": 100,
        "error_rate": 0,
        "latency": 0.03,
        "cpu": 1,
        "memory": 40,
        **extra,
    }


def result(settings, values, errors=0):
    return {r.kind: r for r in evaluate(values, errors, settings)}


@pytest.mark.parametrize(
    "metric,kind,threshold",
    [
        ("error_rate", "http_errors", 10),
        ("latency", "latency", 1),
        ("cpu", "cpu", 80),
        ("memory", "memory", 256),
    ],
)
def test_strict_threshold_boundaries(settings, metric, kind, threshold):
    assert result(settings, metrics(**{metric: threshold}))[kind].breached is False
    assert result(settings, metrics(**{metric: threshold + 0.01}))[kind].breached is True


@pytest.mark.parametrize("traffic", [None, 0, 19])
def test_insufficient_traffic_is_unknown(settings, traffic):
    rules = result(settings, metrics(requests_window=traffic, error_rate=90, latency=2))
    assert rules["http_errors"].breached is None
    assert rules["latency"].breached is None


def test_log_threshold_is_inclusive(settings):
    assert result(settings, metrics(), 4)["error_logs"].breached is False
    assert result(settings, metrics(), 5)["error_logs"].breached is True


def test_prometheus_failure_is_unknown_but_log_rules_still_run(settings):
    rules = result(settings, None, 5)
    assert all(r.breached is None for k, r in rules.items() if k != "error_logs")
    assert rules["error_logs"].breached is True


@pytest.mark.parametrize("up", [None, 0])
def test_missing_scrape_is_unavailable(settings, up):
    rules = result(settings, metrics(up=up))
    assert rules["unavailable"].breached is True
    assert rules["http_errors"].breached is None


def test_missing_metric_not_zero(settings):
    assert result(settings, metrics(memory=None))["memory"].breached is None

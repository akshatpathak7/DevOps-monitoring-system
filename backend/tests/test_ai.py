from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from openai import APITimeoutError
from sqlalchemy import func, select

from app.models import AnalysisAttempt
from app.services.ai_service import AIService, Explanation, build_context, parse_explanation

VALID = {
    "likely_cause": "Dependency failure",
    "explanation": "Errors coincide with failed calls.",
    "troubleshooting_steps": ["Inspect dependency health"],
    "uncertainty_note": "Evidence is limited",
}


def test_structured_parse():
    assert parse_explanation(SimpleNamespace(output_parsed=VALID)).likely_cause == "Dependency failure"


@pytest.mark.parametrize("parsed", [None, {}, {**VALID, "troubleshooting_steps": []}])
def test_refused_or_malformed(parsed):
    with pytest.raises(ValueError):
        parse_explanation(SimpleNamespace(output_parsed=parsed))


async def test_live_success_persists_and_reuses(db, incident, settings):
    service = AIService(settings)
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=Explanation(**VALID)))
    service.client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    await service.analyze(db, incident)
    await service.analyze(db, incident)
    assert incident.analysis_source == "openai"
    assert incident.ai_recommendation == VALID["troubleshooting_steps"]
    parse.assert_awaited_once()
    assert parse.call_args.kwargs["store"] is False
    assert "tools" not in parse.call_args.kwargs
    assert await db.scalar(select(func.count()).select_from(AnalysisAttempt)) == 1


async def test_timeout_does_not_fall_back_and_counts_attempt(db, incident, settings):
    service = AIService(settings)
    service.client = SimpleNamespace(
        responses=SimpleNamespace(
            parse=AsyncMock(side_effect=APITimeoutError(request=httpx.Request("POST", "http://example")))
        )
    )
    with pytest.raises(HTTPException) as exc:
        await service.analyze(db, incident)
    assert exc.value.status_code == 502
    assert incident.analysis_source is None
    assert await db.scalar(select(func.count()).select_from(AnalysisAttempt)) == 1


async def test_attempt_limit_and_concurrency(db, incident, settings):
    service = AIService(settings)
    service.client = SimpleNamespace(responses=SimpleNamespace(parse=AsyncMock()))
    async with service.lock:
        with pytest.raises(HTTPException) as exc:
            await service.analyze(db, incident)
        assert exc.value.status_code == 429
    for _ in range(10):
        db.add(AnalysisAttempt(attempted_at=incident.detected_at))
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await service.analyze(db, incident)
    assert exc.value.status_code == 429
    service.client.responses.parse.assert_not_called()


async def test_context_bounded_and_redacted(incident):
    incident.log_excerpt = [{"message": "token=private " + "x" * 2000}] * 40
    context = build_context(incident)
    assert len(context["logs"]) == 30
    assert len(context["logs"][0]["message"]) == 1000
    assert "private" not in context["logs"][0]["message"]


@pytest.mark.parametrize("parsed", [None, {"explanation": "missing other fields"}])
async def test_invalid_live_result_is_retryable_without_persistence(db, incident, settings, parsed):
    service = AIService(settings)
    service.client = SimpleNamespace(
        responses=SimpleNamespace(parse=AsyncMock(return_value=SimpleNamespace(output_parsed=parsed)))
    )
    with pytest.raises(HTTPException) as exc:
        await service.analyze(db, incident)
    assert exc.value.status_code == 502
    assert incident.analyzed_at is None
    assert incident.ai_explanation is None

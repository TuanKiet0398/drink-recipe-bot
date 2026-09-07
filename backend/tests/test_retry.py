import pytest
from prometheus_client import REGISTRY

from app.retry import retry_once


def _sample(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return 0.0 if value is None else value


def test_retry_once_returns_the_first_successful_result():
    assert retry_once(lambda: "ok", call_type="generate", model="gpt-4o-mini") == "ok"


def test_retry_once_counts_a_retry_when_the_first_attempt_fails():
    calls = {"n": 0}

    def _flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return "recovered"

    before = _sample("llm_retries_total", {"call_type": "embedding"})

    result = retry_once(_flaky, delay_seconds=0, call_type="embedding", model="text-embedding-3-small")

    assert result == "recovered"
    assert _sample("llm_retries_total", {"call_type": "embedding"}) - before == 1


def test_retry_once_counts_an_error_when_both_attempts_fail():
    labels = {"model": "gpt-4o-mini", "call_type": "generate", "outcome": "error"}
    before = _sample("llm_calls_total", labels)

    def _always_fails():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        retry_once(_always_fails, delay_seconds=0, call_type="generate", model="gpt-4o-mini")

    assert _sample("llm_calls_total", labels) - before == 1


def test_retry_once_does_not_count_a_retry_on_first_success():
    before = _sample("llm_retries_total", {"call_type": "rerank"})

    retry_once(lambda: "ok", call_type="rerank", model="gpt-4o-mini")

    assert _sample("llm_retries_total", {"call_type": "rerank"}) - before == 0

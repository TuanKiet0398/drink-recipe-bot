import pytest
from prometheus_client import REGISTRY

from app import metrics


def _sample(name: str, labels: dict[str, str]) -> float:
    value = REGISTRY.get_sample_value(name, labels)
    return 0.0 if value is None else value


def test_record_llm_usage_counts_prompt_and_completion_tokens():
    labels_prompt = {"model": "gpt-4o-mini", "call_type": "generate", "kind": "prompt"}
    labels_completion = {"model": "gpt-4o-mini", "call_type": "generate", "kind": "completion"}
    before_prompt = _sample("llm_tokens_total", labels_prompt)
    before_completion = _sample("llm_tokens_total", labels_completion)

    metrics.record_llm_usage("gpt-4o-mini", "generate", prompt_tokens=100, completion_tokens=50)

    assert _sample("llm_tokens_total", labels_prompt) - before_prompt == 100
    assert _sample("llm_tokens_total", labels_completion) - before_completion == 50


def test_record_llm_usage_computes_cost_for_a_priced_model():
    labels = {"model": "gpt-4o-mini", "call_type": "rerank"}
    before = _sample("llm_cost_usd_total", labels)

    # gpt-4o-mini is priced at (0.15, 0.60) USD per 1M tokens.
    metrics.record_llm_usage("gpt-4o-mini", "rerank", prompt_tokens=1_000_000, completion_tokens=1_000_000)

    assert _sample("llm_cost_usd_total", labels) - before == pytest.approx(0.75)


def test_record_llm_usage_charges_zero_for_an_unknown_model():
    labels = {"model": "totally-made-up-model", "call_type": "generate"}
    before = _sample("llm_cost_usd_total", labels)

    metrics.record_llm_usage(
        "totally-made-up-model", "generate", prompt_tokens=1_000_000, completion_tokens=1_000_000
    )

    assert _sample("llm_cost_usd_total", labels) - before == 0.0


def test_record_llm_usage_handles_a_missing_completion_count():
    labels = {"model": "text-embedding-3-small", "call_type": "embedding", "kind": "prompt"}
    before = _sample("llm_tokens_total", labels)

    metrics.record_llm_usage("text-embedding-3-small", "embedding", prompt_tokens=42, completion_tokens=None)

    assert _sample("llm_tokens_total", labels) - before == 42


def test_record_llm_usage_never_raises_on_bad_input():
    # Application code must survive garbage rather than failing a customer reply.
    metrics.record_llm_usage("gpt-4o-mini", "generate", prompt_tokens="not-a-number", completion_tokens=None)


def test_record_extraction_counts_detected_outcome():
    labels = {"extractor": "favourite", "outcome": "detected"}
    before = _sample("extraction_runs_total", labels)

    metrics.record_extraction("favourite", "detected")

    assert _sample("extraction_runs_total", labels) - before == 1


def test_record_extraction_counts_noop_outcome():
    labels = {"extractor": "customer_notes", "outcome": "noop"}
    before = _sample("extraction_runs_total", labels)

    metrics.record_extraction("customer_notes", "noop")

    assert _sample("extraction_runs_total", labels) - before == 1


def test_record_extraction_never_raises_on_bad_input():
    metrics.record_extraction(None, None)


def test_record_summarize_counts_ran_outcome():
    labels = {"outcome": "ran"}
    before = _sample("summarize_runs_total", labels)

    metrics.record_summarize("ran")

    assert _sample("summarize_runs_total", labels) - before == 1


def test_record_summarize_never_raises_on_bad_input():
    metrics.record_summarize(None)


def test_record_daily_limit_hit_counts_by_channel():
    labels = {"channel_id": "3"}
    before = _sample("daily_token_limit_hits_total", labels)

    metrics.record_daily_limit_hit(3)

    assert _sample("daily_token_limit_hits_total", labels) - before == 1


def test_record_daily_limit_hit_never_raises_on_bad_input():
    metrics.record_daily_limit_hit(None)


def test_model_prices_can_be_overridden_by_environment(monkeypatch):
    monkeypatch.setenv("MODEL_PRICES_JSON", '{"my-model": [1000.0, 2000.0]}')
    prices = metrics.load_model_prices()
    assert prices["my-model"] == (1000.0, 2000.0)


def test_model_prices_ignores_malformed_environment_override(monkeypatch):
    monkeypatch.setenv("MODEL_PRICES_JSON", "{not json")
    prices = metrics.load_model_prices()
    assert "gpt-4o-mini" in prices


def test_record_llm_call_counts_outcomes():
    labels = {"model": "gpt-4o-mini", "call_type": "generate", "outcome": "error"}
    before = _sample("llm_calls_total", labels)

    metrics.record_llm_call("gpt-4o-mini", "generate", "error")

    assert _sample("llm_calls_total", labels) - before == 1


def test_record_retry_counts_retries():
    labels = {"call_type": "embedding"}
    before = _sample("llm_retries_total", labels)

    metrics.record_retry("embedding")

    assert _sample("llm_retries_total", labels) - before == 1


def test_record_telegram_message_counts_by_direction():
    labels = {"channel_id": "7", "direction": "in"}
    before = _sample("telegram_messages_total", labels)

    metrics.record_telegram_message(7, "in")

    assert _sample("telegram_messages_total", labels) - before == 1


def test_record_poll_error_counts_by_channel():
    labels = {"channel_id": "7"}
    before = _sample("telegram_poll_errors_total", labels)

    metrics.record_poll_error(7)

    assert _sample("telegram_poll_errors_total", labels) - before == 1


def test_metrics_endpoint_is_reachable_without_auth(client):
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_exposes_the_expected_collectors(client):
    body = client.get("/metrics").text
    for name in (
        "llm_tokens_total",
        "llm_cost_usd_total",
        "llm_calls_total",
        "llm_retries_total",
        "agent_node_duration_seconds",
        "retrieve_chunks_returned",
        "telegram_messages_total",
        "telegram_poll_errors_total",
        "active_channels",
    ):
        assert name in body


def test_metrics_endpoint_exposes_http_request_metrics(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert "http_request_duration_seconds" in body

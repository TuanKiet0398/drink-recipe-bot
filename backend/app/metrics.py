"""Prometheus collectors for the bot's runtime behaviour.

Every public helper here swallows its own errors. A metrics failure must
never break a customer reply — the same contract `log_token_usage` holds.

Counter names are declared WITHOUT a `_total` suffix: prometheus_client
appends it when rendering, so `Counter("llm_tokens", ...)` is exported as
`llm_tokens_total`.

Cardinality rule: no per-user or per-conversation label. `user_id`,
`telegram_user_id`, `chat_id`, and message text must never become label
values. `channel_id` is allowed — channels are few and admin-created.
"""

import json
import logging
import os
from functools import lru_cache

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# USD per 1M tokens: (prompt, completion). Prices drift, so this is an
# estimate — the provider's bill is authoritative. Override without a
# rebuild by setting MODEL_PRICES_JSON, e.g. {"gpt-4o-mini": [0.15, 0.6]}.
DEFAULT_MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
}


def load_model_prices() -> dict[str, tuple[float, float]]:
    """Merge the MODEL_PRICES_JSON override onto the defaults.

    A malformed override is logged and ignored rather than crashing the
    process at import time.
    """
    prices = dict(DEFAULT_MODEL_PRICES)
    raw = os.getenv("MODEL_PRICES_JSON", "").strip()
    if not raw:
        return prices
    try:
        for model, pair in json.loads(raw).items():
            prompt_price, completion_price = pair
            prices[model] = (float(prompt_price), float(completion_price))
    except Exception:
        logger.exception("Ignoring malformed MODEL_PRICES_JSON")
    return prices


MODEL_PRICES = load_model_prices()

LLM_TOKENS = Counter("llm_tokens", "OpenAI tokens consumed", ["model", "call_type", "kind"])
LLM_COST_USD = Counter("llm_cost_usd", "Estimated OpenAI spend in USD", ["model", "call_type"])
LLM_CALLS = Counter("llm_calls", "OpenAI calls by outcome", ["model", "call_type", "outcome"])
LLM_RETRIES = Counter("llm_retries", "Retried OpenAI calls", ["call_type"])
AGENT_NODE_DURATION = Histogram(
    "agent_node_duration_seconds", "Wall time per LangGraph node", ["node"]
)
RETRIEVE_CHUNKS = Histogram(
    "retrieve_chunks_returned",
    "Chunks surviving retrieval and reranking",
    buckets=(0, 1, 2, 3, 4, 5, 7, 10),
)
TELEGRAM_MESSAGES = Counter(
    "telegram_messages", "Telegram messages handled", ["channel_id", "direction"]
)
TELEGRAM_POLL_ERRORS = Counter(
    "telegram_poll_errors", "Failed Telegram getUpdates calls", ["channel_id"]
)
ACTIVE_CHANNELS = Gauge("active_channels", "Channels with a running poll task")


@lru_cache
def _warn_unknown_model_once(model: str) -> None:
    logger.warning("No price entry for model=%s; recording zero cost", model)


def record_llm_usage(
    model: str, call_type: str, prompt_tokens: int, completion_tokens: int | None
) -> None:
    try:
        prompt = int(prompt_tokens)
        completion = int(completion_tokens) if completion_tokens is not None else 0
        LLM_TOKENS.labels(model=model, call_type=call_type, kind="prompt").inc(prompt)
        if completion:
            LLM_TOKENS.labels(model=model, call_type=call_type, kind="completion").inc(completion)

        price = MODEL_PRICES.get(model)
        if price is None:
            _warn_unknown_model_once(model)
            cost = 0.0
        else:
            cost = (prompt * price[0] + completion * price[1]) / 1_000_000
        LLM_COST_USD.labels(model=model, call_type=call_type).inc(cost)
    except Exception:
        logger.exception("Failed to record LLM usage for model=%s call_type=%s", model, call_type)


def record_llm_call(model: str, call_type: str, outcome: str) -> None:
    try:
        LLM_CALLS.labels(model=model, call_type=call_type, outcome=outcome).inc()
    except Exception:
        logger.exception("Failed to record LLM call for model=%s call_type=%s", model, call_type)


def record_retry(call_type: str) -> None:
    try:
        LLM_RETRIES.labels(call_type=call_type).inc()
    except Exception:
        logger.exception("Failed to record retry for call_type=%s", call_type)

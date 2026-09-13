# EC2 Terraform + Prometheus/Grafana Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the Matcha Bot stack to a single EC2 instance provisioned by Terraform, and instrument the backend so Prometheus and a provisioned Grafana dashboard show host, HTTP, and LLM token/cost/latency metrics.

**Architecture:** The backend exports Prometheus metrics from three existing choke points (`log_token_usage`, `retry_once`, and the LangGraph node registration in `build_graph`), so instrumentation stays local instead of scattered across call sites. A new `docker-compose.prod.yml` pulls published GHCR images and adds Prometheus, Grafana, node_exporter, and cadvisor. Terraform provisions one EC2 instance, an Elastic IP, a security group, and SSM SecureString parameters; a manually triggered GitHub Actions job copies the compose and monitoring files over SSH and restarts the stack.

**Tech Stack:** Python 3.11, FastAPI, `prometheus-client`, `prometheus-fastapi-instrumentator`, Docker Compose, Prometheus, Grafana, Terraform (AWS provider), GitHub Actions, Amazon Linux 2023.

**Spec:** `docs/superpowers/specs/2026-09-07-ec2-terraform-observability-design.md`

## Global Constraints

- Python floor is `>=3.11` (`backend/pyproject.toml`). Do not use syntax newer than 3.11.
- **Metric operations must never raise into application code.** Every call into `app.metrics` from application modules is wrapped so a metrics failure cannot break a customer reply. This mirrors the existing contract of `log_token_usage`, which is documented as "Never raises".
- **Label cardinality rule:** no metric may carry a per-user or per-conversation label. `user_id`, `telegram_user_id`, `chat_id`, and message text are forbidden as label values. `channel_id` is permitted because channels are few and administrator-created.
- **`prometheus_client` naming trap:** `Counter("foo_total", ...)` produces a sample named `foo_total_total`. Declare counters **without** the `_total` suffix; the library appends it. Every counter in this plan is declared without the suffix and queried with it.
- Counters in this plan live in the default `prometheus_client.REGISTRY` and are process-global. Tests must assert on the **delta** between a before-value and an after-value, never on an absolute value, because test order is not guaranteed.
- The deploy workflow keeps `workflow_dispatch` as its **only** trigger. Do not add a `push` trigger.
- Ports published to the EC2 host: `80` (frontend) and `3000` (Grafana) only. Prometheus, cadvisor, node_exporter, and the backend must not publish host ports.
- Backend tests run from the `backend/` directory: `cd backend && pytest`. The suite requires `OPENAI_API_KEY` and `ENCRYPTION_KEY` env vars to be set to any non-empty value (see `.github/workflows/deploy.yml`).

---

### Task 1: Metrics module — collectors, price table, and `record_llm_usage`

**Files:**
- Create: `backend/app/metrics.py`
- Create: `backend/tests/test_metrics.py`
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `LLM_TOKENS: Counter` — labels `model`, `call_type`, `kind`; sample name `llm_tokens_total`
  - `LLM_COST_USD: Counter` — labels `model`, `call_type`; sample name `llm_cost_usd_total`
  - `LLM_CALLS: Counter` — labels `model`, `call_type`, `outcome`; sample name `llm_calls_total`
  - `LLM_RETRIES: Counter` — label `call_type`; sample name `llm_retries_total`
  - `AGENT_NODE_DURATION: Histogram` — label `node`; sample base name `agent_node_duration_seconds`
  - `RETRIEVE_CHUNKS: Histogram` — no labels; sample base name `retrieve_chunks_returned`
  - `TELEGRAM_MESSAGES: Counter` — labels `channel_id`, `direction`; sample name `telegram_messages_total`
  - `TELEGRAM_POLL_ERRORS: Counter` — label `channel_id`; sample name `telegram_poll_errors_total`
  - `ACTIVE_CHANNELS: Gauge` — no labels; sample name `active_channels`
  - `record_llm_usage(model: str, call_type: str, prompt_tokens: int, completion_tokens: int | None) -> None`
  - `record_llm_call(model: str, call_type: str, outcome: str) -> None`
  - `record_retry(call_type: str) -> None`
  - `MODEL_PRICES: dict[str, tuple[float, float]]` — model name to (USD per 1M prompt tokens, USD per 1M completion tokens)

- [ ] **Step 1: Add the dependencies**

In `backend/pyproject.toml`, add to `dependencies`:

```toml
    "prometheus-client>=0.21",
    "prometheus-fastapi-instrumentator>=7.0",
```

And to `[project.optional-dependencies]` `dev`:

```toml
    "ruff>=0.7",
```

Then install:

```bash
cd backend && pip install -e ".[dev]"
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_metrics.py`:

```python
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

    metrics.record_llm_usage("totally-made-up-model", "generate", prompt_tokens=1_000_000, completion_tokens=1_000_000)

    assert _sample("llm_cost_usd_total", labels) - before == 0.0


def test_record_llm_usage_handles_a_missing_completion_count():
    labels = {"model": "text-embedding-3-small", "call_type": "embedding", "kind": "prompt"}
    before = _sample("llm_tokens_total", labels)

    metrics.record_llm_usage("text-embedding-3-small", "embedding", prompt_tokens=42, completion_tokens=None)

    assert _sample("llm_tokens_total", labels) - before == 42


def test_record_llm_usage_never_raises_on_bad_input():
    # Application code must survive garbage rather than failing a customer reply.
    metrics.record_llm_usage("gpt-4o-mini", "generate", prompt_tokens="not-a-number", completion_tokens=None)


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
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.metrics'`

- [ ] **Step 4: Write the implementation**

Create `backend/app/metrics.py`:

```python
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

LLM_TOKENS = Counter(
    "llm_tokens", "OpenAI tokens consumed", ["model", "call_type", "kind"]
)
LLM_COST_USD = Counter(
    "llm_cost_usd", "Estimated OpenAI spend in USD", ["model", "call_type"]
)
LLM_CALLS = Counter(
    "llm_calls", "OpenAI calls by outcome", ["model", "call_type", "outcome"]
)
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
```

Note on `LLM_COST_USD.labels(...).inc(0.0)`: incrementing by zero still creates the label series, which is what the "unknown model" test asserts against.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_metrics.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 6: Run the whole suite**

Run: `cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY= pytest -q`
Expected: PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/metrics.py backend/tests/test_metrics.py backend/pyproject.toml
git commit -m "feat: add Prometheus collectors and LLM cost estimation"
```

---

### Task 2: Record token usage and cost from `log_token_usage`

**Files:**
- Modify: `backend/app/token_usage.py`
- Test: `backend/tests/test_token_usage.py`

**Interfaces:**
- Consumes: `app.metrics.record_llm_usage`, `app.metrics.record_llm_call` from Task 1.
- Produces: no new symbols. `log_token_usage` keeps its existing signature `(db, user_id, call_type, model, usage) -> None` and its "never raises" contract.

`log_token_usage` is the single point every OpenAI call site passes through — `nodes.py:84` (rewrite_query), `:114` (rerank), `:138` (embedding), `:227` (generate), `:243` (extract_favourite). Hooking here covers all five without touching any of them.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_token_usage.py`:

```python
def test_log_token_usage_records_prometheus_metrics(db_session):
    from prometheus_client import REGISTRY

    from app.token_usage import log_token_usage

    class _Usage:
        prompt_tokens = 30
        completion_tokens = 20
        total_tokens = 50

    labels = {"model": "gpt-4o-mini", "call_type": "generate", "kind": "prompt"}
    before = REGISTRY.get_sample_value("llm_tokens_total", labels) or 0.0

    log_token_usage(db_session, None, "generate", "gpt-4o-mini", _Usage())

    after = REGISTRY.get_sample_value("llm_tokens_total", labels) or 0.0
    assert after - before == 30


def test_log_token_usage_records_an_ok_call(db_session):
    from prometheus_client import REGISTRY

    from app.token_usage import log_token_usage

    class _Usage:
        prompt_tokens = 1
        completion_tokens = 1
        total_tokens = 2

    labels = {"model": "gpt-4o-mini", "call_type": "rerank", "outcome": "ok"}
    before = REGISTRY.get_sample_value("llm_calls_total", labels) or 0.0

    log_token_usage(db_session, None, "rerank", "gpt-4o-mini", _Usage())

    after = REGISTRY.get_sample_value("llm_calls_total", labels) or 0.0
    assert after - before == 1


def test_log_token_usage_with_none_usage_records_nothing(db_session):
    from prometheus_client import REGISTRY

    from app.token_usage import log_token_usage

    labels = {"model": "gpt-4o-mini", "call_type": "generate", "kind": "prompt"}
    before = REGISTRY.get_sample_value("llm_tokens_total", labels) or 0.0

    log_token_usage(db_session, None, "generate", "gpt-4o-mini", None)

    after = REGISTRY.get_sample_value("llm_tokens_total", labels) or 0.0
    assert after == before
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_token_usage.py -v`
Expected: FAIL — the token and call counters do not move.

- [ ] **Step 3: Write the implementation**

In `backend/app/token_usage.py`, add the import:

```python
from app.metrics import record_llm_call, record_llm_usage
```

Then, inside `log_token_usage`, after the existing `db.commit()` and still inside the `try` block, add:

```python
        record_llm_usage(model, call_type, int(usage.prompt_tokens), completion_tokens)
        record_llm_call(model, call_type, "ok")
```

The metric helpers already swallow their own errors, and the surrounding `except Exception` keeps the "never raises" contract intact regardless.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_token_usage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/token_usage.py backend/tests/test_token_usage.py
git commit -m "feat: export token and cost metrics from log_token_usage"
```

---

### Task 3: Count retries and failures in `retry_once`

**Files:**
- Modify: `backend/app/retry.py`
- Modify: `backend/app/agent/nodes.py` (5 call sites pass `call_type` and `model`)
- Create: `backend/tests/test_retry.py`

**Interfaces:**
- Consumes: `app.metrics.record_retry`, `app.metrics.record_llm_call` from Task 1.
- Produces: `retry_once(fn, delay_seconds: float = 0.5, call_type: str = "unknown", model: str = "unknown") -> T`. The two new parameters are keyword-friendly and defaulted, so existing positional calls keep working.

`log_token_usage` already records `outcome="ok"`, but it only runs when a call succeeds. `retry_once` is where a definitive failure is observable, so it records `outcome="error"` when both attempts raise.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_retry.py`:

```python
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

    assert retry_once(_flaky, delay_seconds=0, call_type="embedding", model="text-embedding-3-small") == "recovered"

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_retry.py -v`
Expected: FAIL — `retry_once() got an unexpected keyword argument 'call_type'`

- [ ] **Step 3: Write the implementation**

Replace the body of `backend/app/retry.py`:

```python
import time
from typing import Callable, TypeVar

from app.metrics import record_llm_call, record_retry

T = TypeVar("T")


def retry_once(
    fn: Callable[[], T],
    delay_seconds: float = 0.5,
    call_type: str = "unknown",
    model: str = "unknown",
) -> T:
    """Call `fn`, retrying exactly once (after a short delay) on failure.

    If both attempts raise, the exception from the retry is propagated so
    callers (e.g. the webhook handler) can fall back to the friendly error
    reply.

    `call_type` and `model` only label metrics; they never affect control
    flow, and both default so existing call sites keep working.
    """
    try:
        return fn()
    except Exception:
        record_retry(call_type)
        time.sleep(delay_seconds)
        try:
            return fn()
        except Exception:
            record_llm_call(model, call_type, "error")
            raise
```

- [ ] **Step 4: Label the five call sites**

In `backend/app/agent/nodes.py`, pass the labels at each `retry_once` call:

`rewrite_query` (around line 79):

```python
        response = retry_once(_call, call_type="rewrite_query", model=REWRITE_MODEL)
```

`rerank` (around line 113):

```python
        response = retry_once(_call, call_type="rerank", model=RERANK_MODEL)
```

`retrieve._embed` (around line 135):

```python
        response = retry_once(
            lambda: openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text),
            call_type="embedding",
            model=EMBEDDING_MODEL,
        )
```

`generate` (around line 226):

```python
    reply_text, usage = retry_once(_stream_once, call_type="generate", model=model)
```

`extract_favourite` does not use `retry_once` and is left unchanged; its successful calls are still counted through `log_token_usage`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_retry.py tests/test_agent_nodes.py -v`
Expected: PASS. `test_agent_nodes.py` must stay green — the new arguments are keyword-only in practice and defaulted.

- [ ] **Step 6: Commit**

```bash
git add backend/app/retry.py backend/app/agent/nodes.py backend/tests/test_retry.py
git commit -m "feat: count LLM retries and failures in retry_once"
```

---

### Task 4: Time the agent graph nodes and observe retrieved chunk counts

**Files:**
- Modify: `backend/app/agent/graph.py:12-17`
- Modify: `backend/app/agent/nodes.py` (end of `retrieve`)
- Test: `backend/tests/test_agent_graph.py`

**Interfaces:**
- Consumes: `app.metrics.AGENT_NODE_DURATION`, `app.metrics.RETRIEVE_CHUNKS` from Task 1.
- Produces: `app.agent.graph._timed(node_name: str, fn: Callable) -> Callable` — a private wrapper used only inside `build_graph`.

All three nodes are registered in one place, so a single wrapper covers `fetch_history`, `retrieve`, and `generate`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_agent_graph.py`:

```python
def test_graph_nodes_record_duration(db_session, monkeypatch):
    from prometheus_client import REGISTRY

    from app.agent import graph as graph_module
    from app.agent.state import AgentState

    def _fake_node(state, *args, **kwargs):
        return state

    monkeypatch.setattr(graph_module, "fetch_history", _fake_node)
    monkeypatch.setattr(graph_module, "retrieve", _fake_node)
    monkeypatch.setattr(graph_module, "generate", _fake_node)

    labels = {"node": "retrieve"}
    before = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0

    graph_module.run_agent(
        AgentState(user_id=1, chat_id="1", incoming_text="hi"),
        db=db_session,
        chroma_client=None,
        openai_client=None,
    )

    after = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0
    assert after - before == 1


def test_timed_wrapper_records_duration_even_when_the_node_raises():
    from prometheus_client import REGISTRY

    from app.agent.graph import _timed

    labels = {"node": "exploding"}
    before = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0

    def _boom(state):
        raise RuntimeError("node failed")

    wrapped = _timed("exploding", _boom)
    try:
        wrapped({})
    except RuntimeError:
        pass

    after = REGISTRY.get_sample_value("agent_node_duration_seconds_count", labels) or 0.0
    assert after - before == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_agent_graph.py -v`
Expected: FAIL — `cannot import name '_timed'`.

- [ ] **Step 3: Write the implementation**

Replace `backend/app/agent/graph.py`:

```python
from typing import Callable

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agent.nodes import fetch_history, generate, retrieve
from app.agent.state import AgentState
from app.metrics import AGENT_NODE_DURATION


def _timed(node_name: str, fn: Callable) -> Callable:
    """Wrap a graph node so its wall time lands in Prometheus.

    The timer is recorded in a `finally` block, so a node that raises is
    still measured — a slow failure is exactly the case worth seeing.
    """

    def _wrapped(state):
        with AGENT_NODE_DURATION.labels(node=node_name).time():
            return fn(state)

    return _wrapped


def build_graph(db: Session, chroma_client, openai_client, on_delta: Callable[[str], None] | None = None):
    graph = StateGraph(AgentState)

    graph.add_node("fetch_history", _timed("fetch_history", lambda s: fetch_history(s, db)))
    graph.add_node("retrieve", _timed("retrieve", lambda s: retrieve(s, db, chroma_client, openai_client)))
    graph.add_node("generate", _timed("generate", lambda s: generate(s, db, openai_client, on_delta=on_delta)))

    graph.set_entry_point("fetch_history")
    graph.add_edge("fetch_history", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


def run_agent(
    state: AgentState,
    db: Session,
    chroma_client,
    openai_client,
    on_delta: Callable[[str], None] | None = None,
) -> AgentState:
    compiled = build_graph(db, chroma_client, openai_client, on_delta=on_delta)
    result_dict = compiled.invoke(state)
    return AgentState.model_validate(result_dict)
```

`Histogram.time()` is a context manager that observes on exit, including on an exception, which is why no explicit `try`/`finally` is needed.

- [ ] **Step 4: Observe the retrieved chunk count**

In `backend/app/agent/nodes.py`, add to the imports:

```python
from app.metrics import RETRIEVE_CHUNKS
```

And in `retrieve`, replace the final two lines:

```python
    merged = sorted(best_scores, key=best_scores.get, reverse=True)
    state.retrieved_chunks = rerank(state.incoming_text, merged, openai_client, db, state.user_id)[:final_k]
    RETRIEVE_CHUNKS.observe(len(state.retrieved_chunks))
    return state
```

Also observe the empty case in the `except` branch of `retrieve`, so a retrieval failure shows up as a zero rather than as missing data:

```python
        state.retrieved_chunks = []
        RETRIEVE_CHUNKS.observe(0)
        return state
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_agent_graph.py tests/test_agent_nodes.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/graph.py backend/app/agent/nodes.py backend/tests/test_agent_graph.py
git commit -m "feat: time agent graph nodes and observe retrieved chunk counts"
```

---

### Task 5: Count Telegram traffic, poll errors, and active channels

**Files:**
- Modify: `backend/app/telegram_poller.py`
- Modify: `backend/app/routers/webhook.py`
- Modify: `backend/app/channel_manager.py`
- Test: `backend/tests/test_channel_manager.py`
- Test: `backend/tests/test_metrics.py`

**Interfaces:**
- Consumes: `app.metrics.TELEGRAM_MESSAGES`, `app.metrics.TELEGRAM_POLL_ERRORS`, `app.metrics.ACTIVE_CHANNELS` from Task 1.
- Produces: `app.metrics.record_telegram_message(channel_id: int, direction: str) -> None` and `app.metrics.record_poll_error(channel_id: int) -> None`, both added to `app/metrics.py` in this task.

`channel_id` is an integer in the code but must be stringified for the label value; Prometheus labels are strings.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_metrics.py`:

```python
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
```

Append to `backend/tests/test_channel_manager.py`:

```python
async def test_sync_sets_the_active_channels_gauge(db_session, monkeypatch):
    from prometheus_client import REGISTRY

    from app.channel_manager import ChannelManager

    manager = ChannelManager()
    await manager.sync(db_session)

    assert REGISTRY.get_sample_value("active_channels") == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_metrics.py tests/test_channel_manager.py -v`
Expected: FAIL — `module 'app.metrics' has no attribute 'record_telegram_message'`.

- [ ] **Step 3: Add the helpers to `app/metrics.py`**

```python
def record_telegram_message(channel_id: int, direction: str) -> None:
    try:
        TELEGRAM_MESSAGES.labels(channel_id=str(channel_id), direction=direction).inc()
    except Exception:
        logger.exception("Failed to record Telegram message for channel_id=%s", channel_id)


def record_poll_error(channel_id: int) -> None:
    try:
        TELEGRAM_POLL_ERRORS.labels(channel_id=str(channel_id)).inc()
    except Exception:
        logger.exception("Failed to record poll error for channel_id=%s", channel_id)


def set_active_channels(count: int) -> None:
    try:
        ACTIVE_CHANNELS.set(count)
    except Exception:
        logger.exception("Failed to set active_channels gauge")
```

- [ ] **Step 4: Wire the poller**

In `backend/app/telegram_poller.py`, add the import:

```python
from app.metrics import record_poll_error, record_telegram_message
```

In `run_poller`, in the `except Exception` branch around `get_updates`, add `record_poll_error(channel_id)` immediately before the existing `await asyncio.sleep(_ERROR_BACKOFF)`.

In `_handle_update`, count the inbound message only once the update is known to carry usable text — matching the guard `process_telegram_message` already applies. Replace the body of `_handle_update`:

```python
async def _handle_update(channel_id: int, bot_token: str, update: dict) -> None:
    message = update.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    telegram_user_id = str(message.get("from", {}).get("id", ""))
    text = message.get("text", "")

    if chat_id and telegram_user_id and text:
        record_telegram_message(channel_id, "in")

    db = SessionLocal()
    try:
        await process_telegram_message(channel_id, bot_token, chat_id, telegram_user_id, text, db)
    finally:
        db.close()
```

- [ ] **Step 5: Wire the webhook pipeline**

In `backend/app/routers/webhook.py`, add the import:

```python
from app.metrics import record_telegram_message
```

In `process_telegram_message`, after the final delivery block (the `try`/`except` around `deliverer.finalize` / `send_message`) and before the background task is created, add:

```python
    record_telegram_message(channel_id, "out")
```

- [ ] **Step 6: Wire the channel manager**

In `backend/app/channel_manager.py`, add the import:

```python
from app.metrics import set_active_channels
```

At the very end of `ChannelManager.sync`, add:

```python
        set_active_channels(len(self._tasks))
```

And at the end of `stop_all`, add the same call so a shutdown zeroes the gauge:

```python
        set_active_channels(len(self._tasks))
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_metrics.py tests/test_channel_manager.py tests/test_webhook.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/metrics.py backend/app/telegram_poller.py backend/app/routers/webhook.py backend/app/channel_manager.py backend/tests/test_metrics.py backend/tests/test_channel_manager.py
git commit -m "feat: count Telegram traffic, poll errors, and active channels"
```

---

### Task 6: Expose `/metrics` and instrument HTTP traffic

**Files:**
- Create: `backend/app/routers/metrics.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_metrics.py`

**Interfaces:**
- Consumes: everything registered by Tasks 1–5.
- Produces: `GET /metrics` returning the Prometheus text exposition format, unauthenticated.

`/metrics` carries no auth because Prometheus cannot present Basic Auth credentials. It is not externally reachable: `frontend/nginx.conf:6` proxies only `location /admin/`, and `docker-compose.prod.yml` (Task 8) publishes no host port for the backend.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_metrics.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_metrics.py -v`
Expected: FAIL — `/metrics` returns 404.

- [ ] **Step 3: Write the router**

Create `backend/app/routers/metrics.py`:

```python
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus scrape endpoint.

    Deliberately unauthenticated — Prometheus cannot send Basic Auth — and
    deliberately unpublished: nginx proxies only /admin/, and the backend
    binds no host port in production, so this is reachable only from inside
    the Docker network.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

- [ ] **Step 4: Wire it into the app**

In `backend/app/main.py`, extend the router import:

```python
from app.routers import (
    admin_channels,
    admin_docs,
    admin_logs,
    admin_usage,
    admin_users,
    health,
    metrics,
)
```

Add the instrumentator import:

```python
from prometheus_fastapi_instrumentator import Instrumentator
```

After the existing `app.include_router(...)` calls, add:

```python
app.include_router(metrics.router)

# HTTP-level latency/status metrics. `expose()` is not called — the /metrics
# route above already renders the default registry, which this writes into.
Instrumentator().instrument(app)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_metrics.py -v`
Expected: PASS.

- [ ] **Step 6: Run the whole suite and check by hand**

```bash
cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY= pytest -q
```

Then run the server and confirm the endpoint by hand:

```bash
cd backend && uvicorn app.main:app --port 8000 &
sleep 3 && curl -s localhost:8000/metrics | head -30
kill %1
```

Expected: Prometheus text output including `llm_tokens_total` and `http_request_duration_seconds`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/metrics.py backend/app/main.py backend/tests/test_metrics.py
git commit -m "feat: expose /metrics and instrument HTTP requests"
```

---

### Task 7: Ruff configuration and lint clean-up

**Files:**
- Modify: `backend/pyproject.toml`

**Interfaces:**
- Consumes: the `ruff` dev dependency added in Task 1.
- Produces: a lint gate that Task 11 wires into CI.

Doing this before the CI change means CI does not go red on its first run.

- [ ] **Step 1: Add the configuration**

Append to `backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 110
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
ignore = ["B008"]  # FastAPI's Depends() in defaults is the framework's idiom
```

- [ ] **Step 2: Run the linter and see what it says**

Run: `cd backend && ruff check .`
Expected: a list of findings, mostly import ordering.

- [ ] **Step 3: Apply the safe fixes**

```bash
cd backend && ruff check --fix . && ruff format .
```

- [ ] **Step 4: Verify the suite still passes**

Run: `cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY= pytest -q`
Expected: PASS. If formatting changed behaviour, something else is wrong — investigate rather than reverting the tests.

- [ ] **Step 5: Confirm the gate is clean**

```bash
cd backend && ruff check . && ruff format --check .
```
Expected: no findings, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "chore: add ruff config and apply formatting"
```

---

### Task 8: Monitoring configuration — Prometheus, alerts, and a provisioned Grafana dashboard

**Files:**
- Create: `monitoring/prometheus.yml`
- Create: `monitoring/alerts.yml`
- Create: `monitoring/grafana/provisioning/datasources/prometheus.yml`
- Create: `monitoring/grafana/provisioning/dashboards/dashboards.yml`
- Create: `monitoring/grafana/dashboards/matcha-overview.json`

**Interfaces:**
- Consumes: the metric names produced by Tasks 1–6.
- Produces: config consumed by the `prometheus` and `grafana` services in Task 9, and shipped to the host by Task 11.

- [ ] **Step 1: Write the Prometheus config**

Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alerts.yml

scrape_configs:
  - job_name: backend
    metrics_path: /metrics
    static_configs:
      - targets: ["backend:8000"]

  - job_name: node
    static_configs:
      - targets: ["node_exporter:9100"]

  - job_name: cadvisor
    static_configs:
      - targets: ["cadvisor:8080"]

  - job_name: prometheus
    static_configs:
      - targets: ["localhost:9090"]
```

- [ ] **Step 2: Write the alert rules**

Create `monitoring/alerts.yml`. `DAILY_COST_ALERT_USD` is substituted at deploy time is **not** how this works — Prometheus does not expand environment variables in rule files, so the threshold is written literally here and changing it means editing this file. The spec's `daily_cost_alert_usd` Terraform variable therefore only documents the intended value; keep the two in sync by hand.

```yaml
groups:
  - name: matcha
    rules:
      - alert: BackendDown
        expr: up{job="backend"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Backend is not being scraped"

      - alert: HighLLMErrorRate
        expr: >
          sum(rate(llm_calls_total{outcome="error"}[5m]))
          / clamp_min(sum(rate(llm_calls_total[5m])), 0.001) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "More than 10% of OpenAI calls are failing"

      - alert: DailyCostExceeded
        expr: sum(increase(llm_cost_usd_total[24h])) > 5
        labels:
          severity: warning
        annotations:
          summary: "Estimated OpenAI spend over the last 24h exceeded $5"

      - alert: DiskAlmostFull
        expr: >
          node_filesystem_avail_bytes{mountpoint="/rootfs",fstype!~"tmpfs|overlay"}
          / node_filesystem_size_bytes{mountpoint="/rootfs",fstype!~"tmpfs|overlay"} < 0.15
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "Less than 15% free space on the root volume"

      - alert: HighMemory
        expr: >
          (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Host memory usage above 90%"

      - alert: TelegramPollFailing
        expr: sum(rate(telegram_poll_errors_total[5m])) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Telegram getUpdates has been failing for 5 minutes"
```

The `/rootfs` mountpoint matches the node_exporter bind mount configured in Task 9. If that mount path changes, this expression must change with it.

- [ ] **Step 3: Write the Grafana provisioning files**

Create `monitoring/grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

Create `monitoring/grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1

providers:
  - name: matcha
    orgId: 1
    folder: ""
    type: file
    disableDeletion: true
    allowUiUpdates: false
    options:
      path: /var/lib/grafana/dashboards
```

`allowUiUpdates: false` is deliberate: dashboards are edited in git, not by clicking in Grafana, so a container replacement never loses work.

- [ ] **Step 4: Write the dashboard**

Create `monitoring/grafana/dashboards/matcha-overview.json`. Build it from the panel table below. Every panel uses `"datasource": {"type": "prometheus", "uid": "PBFA97CFB590B2093"}` — Grafana resolves a provisioned default datasource by name when the UID is unknown, so if a panel shows "datasource not found", replace the `datasource` value with `"Prometheus"` and reload.

Skeleton — the two panels are complete and show the exact shape every other panel follows:

```json
{
  "uid": "matcha-overview",
  "title": "Matcha Bot Overview",
  "timezone": "browser",
  "schemaVersion": 39,
  "refresh": "30s",
  "time": { "from": "now-6h", "to": "now" },
  "panels": [
    {
      "type": "row",
      "title": "Health",
      "gridPos": { "h": 1, "w": 24, "x": 0, "y": 0 }
    },
    {
      "type": "stat",
      "title": "Targets up",
      "datasource": "Prometheus",
      "gridPos": { "h": 4, "w": 6, "x": 0, "y": 1 },
      "targets": [{ "expr": "sum(up)", "refId": "A" }]
    },
    {
      "type": "timeseries",
      "title": "Host CPU usage",
      "datasource": "Prometheus",
      "gridPos": { "h": 8, "w": 9, "x": 6, "y": 1 },
      "fieldConfig": { "defaults": { "unit": "percentunit", "max": 1 }, "overrides": [] },
      "targets": [
        {
          "expr": "1 - avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m]))",
          "refId": "A",
          "legendFormat": "cpu"
        }
      ]
    }
  ]
}
```

Remaining panels, each following that same shape:

| Row | Panel | Type | `expr` | Unit |
|---|---|---|---|---|
| Health | Host memory usage | timeseries | `1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes` | `percentunit` |
| Health | Root disk free | stat | `node_filesystem_avail_bytes{mountpoint="/rootfs",fstype!~"tmpfs\|overlay"}` | `bytes` |
| Health | Active channels | stat | `active_channels` | `short` |
| HTTP | Request rate | timeseries | `sum(rate(http_requests_total[5m])) by (handler)` | `reqps` |
| HTTP | Latency p50 | timeseries | `histogram_quantile(0.5, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` | `s` |
| HTTP | Latency p95 | timeseries | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` | `s` |
| HTTP | Status codes | timeseries | `sum(rate(http_requests_total[5m])) by (status)` | `reqps` |
| LLM | Tokens by model | timeseries | `sum(rate(llm_tokens_total[5m])) by (model, kind)` | `short` |
| LLM | Estimated cost (24h) | stat | `sum(increase(llm_cost_usd_total[24h]))` | `currencyUSD` |
| LLM | Cost by call type (24h) | barchart | `sum(increase(llm_cost_usd_total[24h])) by (call_type)` | `currencyUSD` |
| LLM | Node latency p95 | timeseries | `histogram_quantile(0.95, sum(rate(agent_node_duration_seconds_bucket[5m])) by (le, node))` | `s` |
| LLM | Call outcomes | timeseries | `sum(rate(llm_calls_total[5m])) by (outcome)` | `short` |
| LLM | Retries | timeseries | `sum(rate(llm_retries_total[5m])) by (call_type)` | `short` |
| LLM | Retrieved chunks (avg) | timeseries | `rate(retrieve_chunks_returned_sum[5m]) / clamp_min(rate(retrieve_chunks_returned_count[5m]), 0.001)` | `short` |
| Telegram | Messages per minute | timeseries | `sum(rate(telegram_messages_total[5m])) * 60 by (channel_id, direction)` | `short` |
| Telegram | Poll errors | timeseries | `sum(rate(telegram_poll_errors_total[5m])) by (channel_id)` | `short` |

Add a `{"type": "row", "title": "HTTP"}`, `{"type": "row", "title": "LLM"}`, and `{"type": "row", "title": "Telegram"}` panel before each group, and give every panel a non-overlapping `gridPos` (the canvas is 24 units wide).

- [ ] **Step 5: Verify the Prometheus config parses**

```bash
docker run --rm -v "$PWD/monitoring:/etc/prometheus:ro" --entrypoint promtool \
  prom/prometheus check config /etc/prometheus/prometheus.yml
docker run --rm -v "$PWD/monitoring:/m" --entrypoint promtool prom/prometheus check rules /m/alerts.yml
```

Expected: `SUCCESS` for both. The config check mounts at `/etc/prometheus` on purpose: `prometheus.yml` refers to `/etc/prometheus/alerts.yml`, and `check config` fails hard (not merely warns) when that path does not resolve inside the container.

- [ ] **Step 6: Verify the dashboard JSON parses**

```bash
python3 -c "import json; json.load(open('monitoring/grafana/dashboards/matcha-overview.json')); print('ok')"
```

- [ ] **Step 7: Commit**

```bash
git add monitoring/
git commit -m "feat: add Prometheus scrape config, alert rules, and Grafana dashboard"
```

---

### Task 9: Production Compose file with the monitoring stack

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `.env.prod.example`

**Interfaces:**
- Consumes: `monitoring/` from Task 8 and the `/metrics` endpoint from Task 6.
- Produces: the file Task 11 copies to `/opt/matcha/docker-compose.prod.yml` on the instance.

`docker-compose.yml` is untouched and stays the local build-from-source file.

- [ ] **Step 1: Write the compose file**

Create `docker-compose.prod.yml`:

```yaml
# Production stack for the EC2 host. Images come from GHCR — nothing is
# built here, because a t3.small cannot build the frontend without
# thrashing. Only ports 80 and 3000 are published; everything else talks
# over the internal Docker network.
services:
  backend:
    image: ghcr.io/${GHCR_REPO}-backend:${IMAGE_TAG:-latest}
    env_file:
      - ./.env
    environment:
      DATABASE_URL: sqlite:////app/data/local.db
      CHROMA_PERSIST_DIR: /app/data/chroma_db
    volumes:
      - backend_data:/app/data
    restart: unless-stopped

  frontend:
    image: ghcr.io/${GHCR_REPO}-frontend:${IMAGE_TAG:-latest}
    depends_on:
      - backend
    ports:
      - "80:80"
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:v2.53.0
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=15d
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/alerts.yml:/etc/prometheus/alerts.yml:ro
      - prom_data:/prometheus
    mem_limit: 400m
    restart: unless-stopped

  grafana:
    image: grafana/grafana:11.1.0
    depends_on:
      - prometheus
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana_data:/var/lib/grafana
    ports:
      - "3000:3000"
    mem_limit: 300m
    restart: unless-stopped

  node_exporter:
    image: prom/node-exporter:v1.8.1
    command:
      - --path.procfs=/host/proc
      - --path.sysfs=/host/sys
      - --path.rootfs=/rootfs
      - --collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    pid: host
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.49.1
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    privileged: true
    devices:
      - /dev/kmsg
    restart: unless-stopped

volumes:
  backend_data:
  prom_data:
  grafana_data:
```

Image tags are pinned rather than floating on `latest` so a redeploy cannot silently change the monitoring stack. `--path.rootfs=/rootfs` is what makes the `mountpoint="/rootfs"` selector in `alerts.yml` correct.

- [ ] **Step 2: Write the env template**

Create `.env.prod.example`:

```bash
# Copied to /opt/matcha/.env on the instance. user_data.sh generates the
# real file from SSM Parameter Store — this template documents the shape.
OPENAI_API_KEY=
ENCRYPTION_KEY=
ADMIN_USERNAME=admin
ADMIN_PASSWORD=
GRAFANA_ADMIN_PASSWORD=

# owner/repo in lowercase, e.g. tuankiet0398/mlops_project
GHCR_REPO=

# Set to a commit SHA to roll back; leave unset for the newest build.
IMAGE_TAG=latest
```

- [ ] **Step 3: Verify the compose file is valid**

```bash
GHCR_REPO=example/repo GRAFANA_ADMIN_PASSWORD=x docker compose -f docker-compose.prod.yml config >/dev/null && echo ok
```

Expected: `ok`.

- [ ] **Step 4: Run the stack locally end to end**

Build local images and tag them so the compose file finds them, then bring the stack up:

```bash
docker build -t ghcr.io/example/repo-backend:latest backend
docker build -t ghcr.io/example/repo-frontend:latest frontend
cp backend/.env .env
printf '\nGHCR_REPO=example/repo\nGRAFANA_ADMIN_PASSWORD=localdev\n' >> .env
docker compose -f docker-compose.prod.yml --env-file .env up -d
```

Wait about 30 seconds, then check:

```bash
curl -sf http://localhost/health && echo "backend ok"
curl -s http://localhost:3000/api/health && echo "grafana ok"
docker compose -f docker-compose.prod.yml exec prometheus \
  wget -qO- 'http://localhost:9090/api/v1/targets?state=active' | grep -o '"health":"[a-z]*"'
```

Expected: the backend and Grafana respond, and every Prometheus target reports `"health":"up"`. Then open `http://localhost:3000`, sign in as `admin` / `localdev`, and confirm the "Matcha Bot Overview" dashboard exists and its Health row has data.

Tear down and remove the throwaway env file:

```bash
docker compose -f docker-compose.prod.yml --env-file .env down -v
rm .env
```

Doing this locally matters — debugging a compose stack over SSH on a `t3.small` is slow.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.prod.yml .env.prod.example
git commit -m "feat: add production compose stack with Prometheus and Grafana"
```

Note: `.gitignore` contains `.env.*` with a `!.env.example` exception, so `.env.prod.example` is ignored. Verify with `git status --short` after `git add`; if the file is not staged, add the exception `!.env.prod.example` to `.gitignore` and include that change in this commit.

---

### Task 10: Terraform infrastructure

**Files:**
- Create: `infra/main.tf`, `infra/variables.tf`, `infra/network.tf`, `infra/compute.tf`, `infra/iam.tf`, `infra/ssm.tf`, `infra/outputs.tf`, `infra/user_data.sh`, `infra/terraform.tfvars.example`, `infra/scripts/put-secrets.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: outputs `public_ip`, `ssh_command`, `grafana_url`, consumed by Task 11's `EC2_HOST` secret and by the README in Task 12.

- [ ] **Step 1: Ignore Terraform state and local variable files**

Append to `.gitignore`:

```
# Terraform — state holds resource IDs and can hold secret values.
infra/.terraform/
infra/*.tfstate
infra/*.tfstate.*
infra/.terraform.lock.hcl
infra/terraform.tfvars
```

- [ ] **Step 2: Write the variables**

Create `infra/variables.tf`:

```hcl
variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-southeast-1"
}

variable "instance_type" {
  description = "EC2 instance type. t3.micro (1GB) cannot hold chromadb plus Grafana plus Prometheus."
  type        = string
  default     = "t3.small"
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size. Holds Docker images, SQLite, Chroma, and 15 days of Prometheus data."
  type        = number
  default     = 30
}

variable "allowed_cidr" {
  description = "Operator's home IP in CIDR form, e.g. 203.0.113.4/32. Grants access to ports 80, 3000, and 22."
  type        = string
}

variable "ssh_public_key" {
  description = "Public half of the deploy keypair. The private .pem goes into the EC2_SSH_KEY GitHub secret."
  type        = string
}

variable "ghcr_username" {
  description = "GitHub username used by the instance to docker login ghcr.io."
  type        = string
}

variable "ghcr_token" {
  description = "GitHub PAT with read:packages, used by the instance to pull private images."
  type        = string
  sensitive   = true
}

variable "ghcr_repo" {
  description = "owner/repo in lowercase, used to build image names."
  type        = string
}

variable "openai_api_key" {
  description = "Stored as an SSM SecureString. Pass via TF_VAR_openai_api_key, never a committed tfvars file."
  type        = string
  sensitive   = true
}

variable "encryption_key" {
  description = "AES-GCM key for channel credentials. Stored as an SSM SecureString."
  type        = string
  sensitive   = true
}

variable "admin_username" {
  description = "Admin dashboard Basic Auth username."
  type        = string
  default     = "admin"
}

variable "admin_password" {
  description = "Admin dashboard Basic Auth password. Stored as an SSM SecureString."
  type        = string
  sensitive   = true
}

variable "grafana_admin_password" {
  description = "Grafana admin password. Stored as an SSM SecureString."
  type        = string
  sensitive   = true
}

variable "project" {
  description = "Name prefix for every resource."
  type        = string
  default     = "matcha"
}
```

- [ ] **Step 3: Write the provider and data sources**

Create `infra/main.tf`:

```hcl
terraform {
  required_version = ">= 1.6"

  required_providers {
    aws  = { source = "hashicorp/aws", version = "~> 5.0" }
    http = { source = "hashicorp/http", version = "~> 3.4" }
  }

  # State is local and gitignored. A single operator does not need a remote
  # backend, and bootstrapping S3 + DynamoDB for state is its own chicken
  # and egg problem. Back the file up by hand; losing it orphans resources.
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# GitHub publishes the CIDR ranges its Actions runners use. The deploy job
# SSHes in from one of them, so port 22 must accept them. The list is large
# and changes over time — re-apply periodically to refresh it.
data "http" "github_meta" {
  url = "https://api.github.com/meta"
}

locals {
  github_actions_cidrs = [
    for cidr in jsondecode(data.http.github_meta.response_body).actions :
    cidr if !strcontains(cidr, ":")
  ]
}
```

The `strcontains` filter drops IPv6 ranges, which `cidr_blocks` cannot accept.

- [ ] **Step 4: Write the security group**

Create `infra/network.tf`:

```hcl
resource "aws_security_group" "app" {
  name        = "${var.project}-app"
  description = "Matcha Bot host: admin UI, Grafana, and SSH"
  vpc_id      = data.aws_vpc.default.id

  # Prometheus (9090), cadvisor, node_exporter and the backend itself are
  # deliberately absent — they publish no host port and are reachable only
  # inside the Docker network.
  ingress {
    description = "Admin SPA"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  ingress {
    description = "Grafana"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_cidr]
  }

  ingress {
    description = "SSH from the operator and from GitHub Actions runners"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = concat([var.allowed_cidr], local.github_actions_cidrs)
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

- [ ] **Step 5: Write the IAM role**

Create `infra/iam.tf`:

```hcl
data "aws_caller_identity" "current" {}

resource "aws_iam_role" "instance" {
  name = "${var.project}-instance"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "read_secrets" {
  name = "${var.project}-read-secrets"
  role = aws_iam_role.instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/${var.project}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = { "kms:ViaService" = "ssm.${var.region}.amazonaws.com" }
        }
      }
    ]
  })
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.project}-instance"
  role = aws_iam_role.instance.name
}
```

- [ ] **Step 6: Write the SSM parameters**

Create `infra/ssm.tf`:

```hcl
# Values arrive through TF_VAR_* environment variables and land in state,
# which is why state is gitignored and must be treated as a secret file.
locals {
  secrets = {
    OPENAI_API_KEY         = var.openai_api_key
    ENCRYPTION_KEY         = var.encryption_key
    ADMIN_USERNAME         = var.admin_username
    ADMIN_PASSWORD         = var.admin_password
    GRAFANA_ADMIN_PASSWORD = var.grafana_admin_password
    GHCR_REPO              = var.ghcr_repo
  }
}

resource "aws_ssm_parameter" "secret" {
  for_each = local.secrets

  name  = "/${var.project}/${each.key}"
  type  = "SecureString"
  value = each.value
}
```

- [ ] **Step 7: Write the instance**

Create `infra/compute.tf`:

```hcl
resource "aws_key_pair" "deploy" {
  key_name   = "${var.project}-deploy"
  public_key = var.ssh_public_key
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]
  key_name               = aws_key_pair.deploy.key_name
  iam_instance_profile   = aws_iam_instance_profile.instance.name

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    project       = var.project
    region        = var.region
    ghcr_username = var.ghcr_username
    ghcr_token    = var.ghcr_token
  })

  # Changing user_data alone should not silently leave a stale host: the
  # instance is replaced so the new bootstrap actually runs.
  user_data_replace_on_change = true

  tags = { Name = "${var.project}-app" }

  depends_on = [aws_ssm_parameter.secret]
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
  tags     = { Name = "${var.project}-app" }
}
```

The Elastic IP means instance replacement does not change `EC2_HOST`.

- [ ] **Step 8: Write the bootstrap script**

Create `infra/user_data.sh`:

```bash
#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y docker fail2ban
# Amazon Linux 2023 ships the compose plugin separately.
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

systemctl enable --now docker
systemctl enable --now fail2ban
usermod -aG docker ec2-user

# Key-only SSH. Port 22 accepts the wide GitHub Actions range, so password
# auth must be off.
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

mkdir -p /opt/matcha
chown ec2-user:ec2-user /opt/matcha

# Render /opt/matcha/.env from SSM. The instance profile allows reading
# only /${project}/*.
aws ssm get-parameters-by-path \
  --region "${region}" \
  --path "/${project}" \
  --with-decryption \
  --query "Parameters[].{n:Name,v:Value}" \
  --output text \
  | awk '{ split($1, parts, "/"); print parts[length(parts)] "=" $2 }' \
  > /opt/matcha/.env
chmod 600 /opt/matcha/.env
chown ec2-user:ec2-user /opt/matcha/.env

echo "${ghcr_token}" | docker login ghcr.io -u "${ghcr_username}" --password-stdin
mkdir -p /root/.docker /home/ec2-user/.docker
cp /root/.docker/config.json /home/ec2-user/.docker/config.json
chown -R ec2-user:ec2-user /home/ec2-user/.docker

cat > /etc/systemd/system/matcha.service <<'UNIT'
[Unit]
Description=Matcha Bot stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/matcha
EnvironmentFile=/opt/matcha/.env
# The compose file arrives with the first deploy, so a boot before that
# must not fail the unit.
ExecStart=/bin/bash -c 'test -f docker-compose.prod.yml && docker compose -f docker-compose.prod.yml up -d || true'
ExecStop=/bin/bash -c 'test -f docker-compose.prod.yml && docker compose -f docker-compose.prod.yml down || true'

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable matcha.service
```

- [ ] **Step 9: Write the outputs and the tfvars template**

Create `infra/outputs.tf`:

```hcl
output "public_ip" {
  description = "Elastic IP. Put this in the EC2_HOST GitHub secret."
  value       = aws_eip.app.public_ip
}

output "ssh_command" {
  description = "Ready-to-paste SSH command."
  value       = "ssh -i matcha-deploy.pem ec2-user@${aws_eip.app.public_ip}"
}

output "grafana_url" {
  description = "Grafana, reachable only from allowed_cidr."
  value       = "http://${aws_eip.app.public_ip}:3000"
}

output "admin_url" {
  description = "Admin SPA, reachable only from allowed_cidr."
  value       = "http://${aws_eip.app.public_ip}"
}
```

Create `infra/terraform.tfvars.example`:

```hcl
# Copy to terraform.tfvars (gitignored) and fill in. Secret values are
# better passed as TF_VAR_* environment variables so they never touch disk:
#
#   export TF_VAR_openai_api_key=sk-...
#   export TF_VAR_encryption_key=...
#   export TF_VAR_admin_password=...
#   export TF_VAR_grafana_admin_password=...
#   export TF_VAR_ghcr_token=ghp_...
#   export TF_VAR_allowed_cidr="$(curl -s ifconfig.me)/32"

region         = "ap-southeast-1"
instance_type  = "t3.small"
allowed_cidr   = "203.0.113.4/32"
ssh_public_key = "ssh-ed25519 AAAA... matcha-deploy"
ghcr_username  = "your-github-username"
ghcr_repo      = "your-github-username/mlops_project"
```

- [ ] **Step 10: Write the secret-loading helper**

Create `infra/scripts/put-secrets.sh`:

```bash
#!/usr/bin/env bash
# Exports the values in backend/.env as TF_VAR_* so `terraform apply` can
# store them in SSM without retyping. Source it, don't run it:
#
#   source infra/scripts/put-secrets.sh
set -euo pipefail

ENV_FILE="${1:-backend/.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "No such env file: $ENV_FILE" >&2
  return 1 2>/dev/null || exit 1
fi

while IFS='=' read -r key value; do
  [[ -z "$key" || "$key" == \#* ]] && continue
  case "$key" in
    OPENAI_API_KEY)  export TF_VAR_openai_api_key="$value" ;;
    ENCRYPTION_KEY)  export TF_VAR_encryption_key="$value" ;;
    ADMIN_USERNAME)  export TF_VAR_admin_username="$value" ;;
    ADMIN_PASSWORD)  export TF_VAR_admin_password="$value" ;;
  esac
done < "$ENV_FILE"

export TF_VAR_allowed_cidr="$(curl -s ifconfig.me)/32"
echo "Exported TF_VAR_* from $ENV_FILE; allowed_cidr=$TF_VAR_allowed_cidr"
echo "Still needed: TF_VAR_grafana_admin_password, TF_VAR_ghcr_token, TF_VAR_ssh_public_key"
```

Make it executable: `chmod +x infra/scripts/put-secrets.sh`

- [ ] **Step 11: Validate the configuration**

```bash
cd infra && terraform init && terraform fmt -check && terraform validate
```

Expected: `Success! The configuration is valid.` `terraform validate` needs the providers downloaded but no AWS credentials.

- [ ] **Step 12: Commit**

```bash
git add infra/ .gitignore
git commit -m "feat: add Terraform config for the EC2 host"
```

Applying this is a manual operator step documented in Task 12, not part of the implementation.

---

### Task 11: CI gates and the deploy job

**Files:**
- Modify: `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `backend/pyproject.toml` ruff config (Task 7), `monitoring/` (Task 8), `docker-compose.prod.yml` (Task 9), `infra/` (Task 10).
- Produces: a `deploy` job gated on a successful health check.

- [ ] **Step 1: Add the new checks to the `test` job**

In `.github/workflows/deploy.yml`, after the existing "Run backend tests" step, insert:

```yaml
      - name: Lint backend
        working-directory: backend
        run: |
          ruff check .
          ruff format --check .

      - name: Validate Prometheus config
        run: |
          docker run --rm -v "$PWD/monitoring:/m" --entrypoint promtool prom/prometheus check rules /m/alerts.yml
          docker run --rm -v "$PWD/monitoring:/etc/prometheus:ro" --entrypoint promtool \
            prom/prometheus check config /etc/prometheus/prometheus.yml

      - name: Validate production compose file
        env:
          GHCR_REPO: example/repo
          GRAFANA_ADMIN_PASSWORD: placeholder
        run: docker compose -f docker-compose.prod.yml config >/dev/null

      - name: Validate Terraform
        run: |
          curl -fsSL https://releases.hashicorp.com/terraform/1.9.5/terraform_1.9.5_linux_amd64.zip -o /tmp/tf.zip
          unzip -q /tmp/tf.zip -d /tmp && sudo mv /tmp/terraform /usr/local/bin/
          cd infra && terraform init -backend=false && terraform fmt -check && terraform validate
```

`terraform plan` is deliberately absent: it would require AWS credentials in CI.

- [ ] **Step 2: Add the deploy job**

Append to `.github/workflows/deploy.yml`:

```yaml
  deploy:
    needs: build-and-push
    runs-on: ubuntu-latest
    environment: production
    steps:
      - uses: actions/checkout@v4

      - name: Set up the SSH key
        run: |
          mkdir -p ~/.ssh
          printf '%s\n' "${{ secrets.EC2_SSH_KEY }}" > ~/.ssh/deploy.pem
          chmod 600 ~/.ssh/deploy.pem
          ssh-keyscan -H "${{ secrets.EC2_HOST }}" >> ~/.ssh/known_hosts

      # Shipping monitoring/ on every deploy is what keeps the Prometheus
      # and Grafana configuration in git rather than hand-edited on the host.
      - name: Copy compose and monitoring config
        run: |
          scp -i ~/.ssh/deploy.pem -r \
            docker-compose.prod.yml monitoring \
            "${{ secrets.EC2_USER }}@${{ secrets.EC2_HOST }}:/opt/matcha/"

      - name: Pull images and restart the stack
        run: |
          ssh -i ~/.ssh/deploy.pem "${{ secrets.EC2_USER }}@${{ secrets.EC2_HOST }}" \
            'set -euo pipefail
             cd /opt/matcha
             set -a && . ./.env && set +a
             docker compose -f docker-compose.prod.yml pull
             docker compose -f docker-compose.prod.yml up -d
             docker image prune -f'

      - name: Wait for the backend to report healthy
        run: |
          ssh -i ~/.ssh/deploy.pem "${{ secrets.EC2_USER }}@${{ secrets.EC2_HOST }}" \
            'for i in $(seq 1 30); do
               if curl -sf http://localhost/health >/dev/null; then
                 echo "healthy after $i attempts"; exit 0
               fi
               sleep 2
             done
             echo "backend never became healthy"; exit 1'
```

- [ ] **Step 3: Confirm the trigger is unchanged**

Run: `grep -A3 '^on:' .github/workflows/deploy.yml`
Expected: `workflow_dispatch: {}` and nothing else. No `push` trigger.

- [ ] **Step 4: Check the workflow parses**

```bash
python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy.yml')); print('ok')"
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add lint/config gates and an SSH deploy job with a health check"
```

---

### Task 12: Operator documentation

**Files:**
- Create: `infra/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing consumed by code.

- [ ] **Step 1: Write the infra README**

Create `infra/README.md`:

````markdown
# Infrastructure

One EC2 instance running the whole stack as containers, provisioned by
Terraform. State is local and gitignored — back up `infra/terraform.tfstate`
by hand, because losing it orphans the resources.

## First-time bootstrap

1. Configure AWS credentials:

   ```bash
   aws configure
   ```

2. Generate the deploy keypair:

   ```bash
   ssh-keygen -t ed25519 -f matcha-deploy -C matcha-deploy -N ""
   ```

   `matcha-deploy` (the private half) goes into the `EC2_SSH_KEY` GitHub
   secret. `matcha-deploy.pub` goes into `TF_VAR_ssh_public_key`.

3. Export the variables:

   ```bash
   source infra/scripts/put-secrets.sh
   export TF_VAR_ssh_public_key="$(cat matcha-deploy.pub)"
   export TF_VAR_grafana_admin_password='pick-something-strong'
   export TF_VAR_ghcr_token='ghp_...'          # needs read:packages
   export TF_VAR_ghcr_username='your-username'
   export TF_VAR_ghcr_repo='your-username/mlops_project'
   ```

4. Apply:

   ```bash
   cd infra && terraform init && terraform apply
   ```

5. Put the `public_ip` output into the `EC2_HOST` GitHub secret, alongside
   `EC2_USER` (`ec2-user`), `EC2_SSH_KEY`, and `GHCR_TOKEN`.

6. Run the `Deploy` workflow manually from the Actions tab.

7. Open the `grafana_url` output and sign in as `admin` with
   `TF_VAR_grafana_admin_password`. The "Matcha Bot Overview" dashboard is
   already provisioned.

## Routine operations

**Your home IP changed.** Re-apply with the new value; only the security
group changes, and the instance is untouched:

```bash
export TF_VAR_allowed_cidr="$(curl -s ifconfig.me)/32"
cd infra && terraform apply
```

**GitHub's Actions IP ranges changed** and deploys started timing out.
Re-apply — the ranges are read live from `api.github.com/meta` on every
plan:

```bash
cd infra && terraform apply
```

**Roll back to an earlier build.** Images are tagged with both `latest` and
the commit SHA:

```bash
ssh -i matcha-deploy.pem ec2-user@<ip>
cd /opt/matcha
sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=<old-sha>/' .env
set -a && . ./.env && set +a
docker compose -f docker-compose.prod.yml up -d
```

**Change an alert threshold or a dashboard panel.** Edit the file under
`monitoring/`, commit, and run the `Deploy` workflow — the deploy copies
`monitoring/` to the host every time. Do not edit dashboards in the Grafana
UI; `allowUiUpdates` is off and edits would be lost.

**Change a model price.** Set `MODEL_PRICES_JSON` in `/opt/matcha/.env`,
e.g. `MODEL_PRICES_JSON={"gpt-4o-mini":[0.15,0.6]}`, then restart the
backend. No rebuild needed.

## Known trade-offs

- Single instance: replacing it means downtime, and the Docker volumes are
  not backed up.
- Local Terraform state: no locking, no history, no team access.
- Port 22 accepts the whole GitHub Actions range, which is wide. Key-only
  authentication and fail2ban are the mitigations; moving the deploy job to
  SSM Run Command would remove the exposure entirely.
- Cost figures in Grafana are estimates from a hard-coded price table. The
  provider's bill is authoritative.
````

- [ ] **Step 2: Update the root README**

In `README.md`, add `Prometheus + Grafana` and `Terraform (EC2)` rows to the stack table, replacing the existing `Infra` row:

```markdown
| Infra | Docker Compose, Terraform (single EC2), GitHub Actions CI/CD |
| Monitoring | Prometheus, Grafana, node_exporter, cadvisor |
```

Add `infra/` and `monitoring/` to the "Project layout" block:

```
infra/                 # Terraform: EC2, security group, Elastic IP, SSM secrets
monitoring/            # Prometheus scrape config + alert rules, provisioned Grafana dashboard
docker-compose.prod.yml  # production stack (GHCR images + monitoring), used on EC2
```

And add a "Deployment" section pointing at `infra/README.md`:

```markdown
## Deployment

The production stack runs on a single EC2 instance provisioned by Terraform.
See [`infra/README.md`](infra/README.md) for bootstrap, rollback, and routine
operations. Deploys are manual: run the `Deploy` workflow from the Actions tab.

Metrics are exported at `/metrics` (unauthenticated, but not published outside
the Docker network) and rendered by a provisioned Grafana dashboard on port 3000.
```

- [ ] **Step 3: Commit**

```bash
git add infra/README.md README.md
git commit -m "docs: document infrastructure bootstrap and operations"
```

---

## Verification checklist

After all tasks are done:

- [ ] `cd backend && OPENAI_API_KEY=test-key-not-real ENCRYPTION_KEY= pytest -q` — the whole suite passes
- [ ] `cd backend && ruff check . && ruff format --check .` — clean
- [ ] `cd infra && terraform fmt -check && terraform validate` — clean
- [ ] `docker compose -f docker-compose.prod.yml config` — valid with `GHCR_REPO` and `GRAFANA_ADMIN_PASSWORD` set
- [ ] `promtool check config` (mounted at `/etc/prometheus`) and `promtool check rules` — SUCCESS
- [ ] The stack runs locally, all Prometheus targets report `up`, and the Grafana dashboard has data (Task 9 Step 4)
- [ ] `grep -A3 '^on:' .github/workflows/deploy.yml` shows `workflow_dispatch` only
- [ ] No metric anywhere carries `user_id`, `telegram_user_id`, `chat_id`, or message text as a label

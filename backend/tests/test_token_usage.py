from app.db.models import TokenUsage
from app.token_usage import log_token_usage


def test_token_usage_model_persists_all_fields(db_session):
    row = TokenUsage(
        user_id=None,
        call_type="embedding",
        model="text-embedding-3-small",
        prompt_tokens=10,
        completion_tokens=None,
        total_tokens=10,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    assert row.id is not None
    assert row.user_id is None
    assert row.call_type == "embedding"
    assert row.model == "text-embedding-3-small"
    assert row.prompt_tokens == 10
    assert row.completion_tokens is None
    assert row.total_tokens == 10
    assert row.created_at is not None


class _FakeUsage:
    def __init__(self, prompt_tokens, total_tokens, completion_tokens=None):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


def test_log_token_usage_writes_a_row_for_a_chat_call(db_session):
    usage = _FakeUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)

    log_token_usage(db_session, user_id=7, call_type="generate", model="gpt-4o-mini", usage=usage)

    rows = db_session.query(TokenUsage).all()
    assert len(rows) == 1
    assert rows[0].user_id == 7
    assert rows[0].call_type == "generate"
    assert rows[0].model == "gpt-4o-mini"
    assert rows[0].prompt_tokens == 100
    assert rows[0].completion_tokens == 50
    assert rows[0].total_tokens == 150


def test_log_token_usage_writes_null_completion_tokens_for_embedding_call(db_session):
    usage = _FakeUsage(prompt_tokens=20, total_tokens=20, completion_tokens=None)

    log_token_usage(db_session, user_id=None, call_type="embedding", model="text-embedding-3-small", usage=usage)

    row = db_session.query(TokenUsage).one()
    assert row.user_id is None
    assert row.completion_tokens is None
    assert row.total_tokens == 20


def test_log_token_usage_is_a_noop_when_usage_is_none(db_session):
    log_token_usage(db_session, user_id=1, call_type="generate", model="gpt-4o-mini", usage=None)

    assert db_session.query(TokenUsage).count() == 0


def test_log_token_usage_swallows_a_malformed_usage_object_and_leaves_session_usable(db_session):
    # An object with none of the expected attributes — simulates a test
    # double that didn't configure `.usage` at all.
    log_token_usage(db_session, user_id=1, call_type="generate", model="gpt-4o-mini", usage=object())

    assert db_session.query(TokenUsage).count() == 0
    # The session must still be usable afterward — a prior failed flush
    # left uncommitted/rolled-back, not the session itself broken.
    db_session.add(TokenUsage(user_id=1, call_type="generate", model="gpt-4o-mini", prompt_tokens=1, total_tokens=1))
    db_session.commit()
    assert db_session.query(TokenUsage).count() == 1


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

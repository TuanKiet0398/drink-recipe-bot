from app.db.models import TokenUsage


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

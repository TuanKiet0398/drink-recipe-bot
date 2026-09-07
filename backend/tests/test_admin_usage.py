from app.db.models import AdminAuditLog, TokenUsage


def test_usage_list_requires_auth(client):
    assert client.get("/admin/usage").status_code == 401


def test_usage_summary_requires_auth(client):
    assert client.get("/admin/usage/summary").status_code == 401


def test_usage_list_returns_rows_newest_first(client, db_session):
    db_session.add(
        TokenUsage(
            user_id=1,
            call_type="generate",
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
        )
    )
    db_session.add(
        TokenUsage(
            user_id=1, call_type="embedding", model="text-embedding-3-small", prompt_tokens=3, total_tokens=3
        )
    )
    db_session.commit()

    response = client.get("/admin/usage", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["call_type"] == "embedding"
    assert body[0]["completion_tokens"] is None
    assert body[1]["call_type"] == "generate"
    assert body[1]["completion_tokens"] == 5


def test_usage_list_respects_limit_and_offset(client, db_session):
    for i in range(3):
        db_session.add(TokenUsage(call_type="generate", model="gpt-4o-mini", prompt_tokens=i, total_tokens=i))
    db_session.commit()

    response = client.get("/admin/usage?limit=1&offset=1", auth=("admin", "admin"))
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_usage_summary_aggregates_totals_and_cost_by_model(client, db_session):
    db_session.add(
        TokenUsage(
            call_type="generate",
            model="gpt-4o-mini",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            total_tokens=1_000_000,
        )
    )
    db_session.add(
        TokenUsage(
            call_type="embedding",
            model="text-embedding-3-small",
            prompt_tokens=1_000_000,
            total_tokens=1_000_000,
        )
    )
    db_session.commit()

    response = client.get("/admin/usage/summary", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()

    assert body["total_calls"] == 2
    assert body["total_tokens"] == 2_000_000
    assert body["estimated_cost_usd"] == 0.17  # 0.15 (1M gpt-4o-mini prompt) + 0.02 (1M embedding)

    by_model = {row["model"]: row for row in body["by_model"]}
    assert by_model["gpt-4o-mini"]["calls"] == 1
    assert by_model["gpt-4o-mini"]["total_tokens"] == 1_000_000
    assert by_model["gpt-4o-mini"]["estimated_cost_usd"] == 0.15
    assert by_model["text-embedding-3-small"]["estimated_cost_usd"] == 0.02


def test_usage_summary_unknown_model_contributes_zero_cost(client, db_session):
    db_session.add(
        TokenUsage(
            call_type="generate", model="some-future-model", prompt_tokens=1_000_000, total_tokens=1_000_000
        )
    )
    db_session.commit()

    response = client.get("/admin/usage/summary", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body["estimated_cost_usd"] == 0.0
    assert body["by_model"][0]["estimated_cost_usd"] == 0.0


def test_usage_summary_with_no_rows(client, db_session):
    response = client.get("/admin/usage/summary", auth=("admin", "admin"))
    assert response.status_code == 200
    body = response.json()
    assert body == {"total_calls": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "by_model": []}


def test_delete_usage_entry_requires_auth(client, db_session):
    entry = TokenUsage(call_type="generate", model="gpt-4o-mini", prompt_tokens=1, total_tokens=1)
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    assert client.delete(f"/admin/usage/{entry.id}").status_code == 401


def test_delete_usage_entry(client, db_session):
    entry = TokenUsage(call_type="generate", model="gpt-4o-mini", prompt_tokens=1, total_tokens=1)
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    response = client.delete(f"/admin/usage/{entry.id}", auth=("admin", "admin"))
    assert response.status_code == 204
    assert db_session.query(TokenUsage).filter_by(id=entry.id).count() == 0


def test_delete_usage_entry_returns_404_when_missing(client, db_session):
    response = client.delete("/admin/usage/999", auth=("admin", "admin"))
    assert response.status_code == 404


def test_clear_usage(client, db_session):
    db_session.add(TokenUsage(call_type="generate", model="gpt-4o-mini", prompt_tokens=1, total_tokens=1))
    db_session.add(
        TokenUsage(call_type="embedding", model="text-embedding-3-small", prompt_tokens=1, total_tokens=1)
    )
    db_session.commit()

    response = client.delete("/admin/usage", auth=("admin", "admin"))
    assert response.status_code == 204
    assert db_session.query(TokenUsage).count() == 0
    logs = db_session.query(AdminAuditLog).filter_by(action="clear_usage").all()
    assert len(logs) == 1

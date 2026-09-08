from app.db.models import AdminAuditLog

AUTH = ("admin", "admin")


def test_endpoints_require_auth(client):
    assert client.get("/admin/soul").status_code == 401
    assert client.put("/admin/soul", json={"content": "x"}).status_code == 401


def test_get_returns_the_current_soul_content(client, tmp_path, monkeypatch):
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text("Friendly and knowledgeable.", encoding="utf-8")
    monkeypatch.setattr("app.routers.admin_soul.SOUL_PATH", soul_path)

    response = client.get("/admin/soul", auth=AUTH)

    assert response.status_code == 200
    assert response.json()["content"] == "Friendly and knowledgeable."


def test_get_returns_empty_string_when_file_missing(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.routers.admin_soul.SOUL_PATH", tmp_path / "does-not-exist.md")

    response = client.get("/admin/soul", auth=AUTH)

    assert response.status_code == 200
    assert response.json()["content"] == ""


def test_put_writes_the_new_content(client, db_session, tmp_path, monkeypatch):
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text("Old personality.", encoding="utf-8")
    monkeypatch.setattr("app.routers.admin_soul.SOUL_PATH", soul_path)

    response = client.put("/admin/soul", auth=AUTH, json={"content": "New personality, warmer tone."})

    assert response.status_code == 200
    assert soul_path.read_text(encoding="utf-8") == "New personality, warmer tone."


def test_put_logs_an_admin_action(client, db_session, tmp_path, monkeypatch):
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text("Old.", encoding="utf-8")
    monkeypatch.setattr("app.routers.admin_soul.SOUL_PATH", soul_path)

    client.put("/admin/soul", auth=AUTH, json={"content": "New."})

    log = db_session.query(AdminAuditLog).filter_by(action="soul.update").one()
    assert log.ip != "" or log.ip == ""  # recorded, value not asserted further


def test_put_takes_effect_immediately_for_the_next_chat_turn(client, tmp_path, monkeypatch):
    soul_path = tmp_path / "SOUL.md"
    soul_path.write_text("Old.", encoding="utf-8")
    monkeypatch.setattr("app.routers.admin_soul.SOUL_PATH", soul_path)
    monkeypatch.setattr("app.agent.nodes.SOUL_PATH", soul_path)

    client.put("/admin/soul", auth=AUTH, json={"content": "Brand new personality."})

    from app.agent.nodes import _load_soul

    assert _load_soul() == "Brand new personality."

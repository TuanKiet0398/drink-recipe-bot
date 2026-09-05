import base64
import glob
import importlib.util
import secrets

import pytest
import sqlalchemy as sa


def _load_backfill_function():
    [path] = [p for p in glob.glob("migrations/versions/*.py") if "channels" in p]
    spec = importlib.util.spec_from_file_location("migration_0003", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._backfill_users_channel


@pytest.fixture()
def _fake_encryption_key(monkeypatch):
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    from app import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture()
def _bare_connection():
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE channels (id INTEGER PRIMARY KEY, key TEXT, display_name TEXT, "
                "channel_type TEXT, encrypted_credentials TEXT, is_active BOOLEAN, created_at DATETIME)"
            )
        )
        connection.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, channel_id INTEGER)"))
        yield connection


def test_backfill_raises_when_users_exist_and_no_token(monkeypatch, _fake_encryption_key, _bare_connection):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    _bare_connection.execute(sa.text("INSERT INTO users (id, channel_id) VALUES (1, NULL)"))

    backfill = _load_backfill_function()
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        backfill(_bare_connection)


def test_backfill_noop_when_no_users_and_no_token(monkeypatch, _fake_encryption_key, _bare_connection):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    backfill = _load_backfill_function()
    backfill(_bare_connection)

    assert _bare_connection.execute(sa.text("SELECT COUNT(*) FROM channels")).scalar() == 0


def test_backfill_creates_legacy_channel_and_attaches_existing_users(
    monkeypatch, _fake_encryption_key, _bare_connection
):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "legacy-token-value")
    _bare_connection.execute(sa.text("INSERT INTO users (id, channel_id) VALUES (1, NULL)"))
    _bare_connection.execute(sa.text("INSERT INTO users (id, channel_id) VALUES (2, NULL)"))

    backfill = _load_backfill_function()
    backfill(_bare_connection)

    channels = _bare_connection.execute(sa.text("SELECT key, channel_type FROM channels")).fetchall()
    assert channels == [("legacy-telegram", "telegram")]

    channel_ids = _bare_connection.execute(sa.text("SELECT DISTINCT channel_id FROM users")).fetchall()
    assert len(channel_ids) == 1
    assert channel_ids[0][0] is not None

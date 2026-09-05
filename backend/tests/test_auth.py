from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_admin
from app.db.base import get_db


def test_require_admin_rejects_bad_credentials(monkeypatch):
    from app import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    config.get_settings.cache_clear()

    probe = FastAPI()

    # require_admin logs failed attempts via a db session — stub it out with
    # a MagicMock so this unit test never touches a real database.
    def _fake_get_db():
        yield MagicMock()

    probe.dependency_overrides[get_db] = _fake_get_db

    @probe.get("/probe")
    def probe_route(user: str = Depends(require_admin)):
        return {"user": user}

    client = TestClient(probe)

    ok = client.get("/probe", auth=("admin", "secret"))
    assert ok.status_code == 200
    assert ok.json() == {"user": "admin"}

    bad = client.get("/probe", auth=("admin", "wrong"))
    assert bad.status_code == 401

    config.get_settings.cache_clear()

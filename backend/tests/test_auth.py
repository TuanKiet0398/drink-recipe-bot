from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import hash_password, require_account, require_admin, verify_password
from app.db.base import get_db
from app.db.models import Account


def test_verify_password_accepts_the_right_password_only():
    stored = hash_password("matcha-lover")

    assert verify_password("matcha-lover", stored)
    assert not verify_password("matcha-lovers", stored)


def test_hash_password_salts_each_hash():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_password_rejects_malformed_stored_values():
    for stored in ["", "plain-text", "scrypt$nothex$nothex", "bcrypt$00$00", None]:
        assert not verify_password("anything", stored)


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


def test_require_admin_rejects_a_self_registered_customer_account(db_session):
    db_session.add(Account(username="linh", password_hash=hash_password("matcha-lover")))
    db_session.commit()

    probe = FastAPI()

    def _fake_get_db():
        yield db_session

    probe.dependency_overrides[get_db] = _fake_get_db

    @probe.get("/probe")
    def probe_route(user: str = Depends(require_admin)):
        return {"user": user}

    client = TestClient(probe)

    response = client.get("/probe", auth=("linh", "matcha-lover"))
    assert response.status_code == 403


def test_require_account_accepts_a_self_registered_customer_account(db_session):
    db_session.add(Account(username="linh", password_hash=hash_password("matcha-lover")))
    db_session.commit()

    probe = FastAPI()

    def _fake_get_db():
        yield db_session

    probe.dependency_overrides[get_db] = _fake_get_db

    @probe.get("/probe")
    def probe_route(user: str = Depends(require_account)):
        return {"user": user}

    client = TestClient(probe)

    response = client.get("/probe", auth=("linh", "matcha-lover"))
    assert response.status_code == 200
    assert response.json() == {"user": "linh"}

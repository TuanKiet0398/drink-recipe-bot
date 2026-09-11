import pytest

from app.config import get_settings
from app.db.models import Account, AdminAuditLog


def test_register_creates_an_account_with_a_hashed_password(client, db_session):
    response = client.post("/auth/register", json={"username": "linh.tran", "password": "matcha-lover"})

    assert response.status_code == 201
    assert response.json() == {"username": "linh.tran"}
    account = db_session.query(Account).filter_by(username="linh.tran").one()
    assert account.password_hash.startswith("scrypt$")
    assert "matcha-lover" not in account.password_hash


def test_register_rejects_a_taken_username(client):
    client.post("/auth/register", json={"username": "linh", "password": "matcha-lover"})

    response = client.post("/auth/register", json={"username": "linh", "password": "another-pass"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already taken"


def test_register_rejects_the_env_admin_username(client):
    response = client.post(
        "/auth/register", json={"username": get_settings().admin_username, "password": "matcha-lover"}
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"username": "ab", "password": "matcha-lover"},
        {"username": "has space", "password": "matcha-lover"},
        {"username": "x" * 33, "password": "matcha-lover"},
        {"username": "linh", "password": "7chars!"},
    ],
)
def test_register_validates_username_and_password(client, body):
    assert client.post("/auth/register", json=body).status_code == 422


def test_register_writes_an_audit_entry(client, db_session):
    client.post("/auth/register", json={"username": "linh", "password": "matcha-lover"})

    entry = db_session.query(AdminAuditLog).filter_by(action="account.register").one()
    assert entry.target == "linh"


def test_a_registered_account_can_use_the_admin_api(client):
    client.post("/auth/register", json={"username": "linh", "password": "matcha-lover"})

    assert client.post("/admin/login", auth=("linh", "matcha-lover")).status_code == 200
    assert client.post("/admin/login", auth=("linh", "wrong-password")).status_code == 401


def test_the_env_admin_still_signs_in_when_accounts_exist(client):
    client.post("/auth/register", json={"username": "linh", "password": "matcha-lover"})
    settings = get_settings()

    response = client.post("/admin/login", auth=(settings.admin_username, settings.admin_password))

    assert response.status_code == 200

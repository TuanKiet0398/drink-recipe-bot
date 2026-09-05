import base64
import secrets

import pytest
from cryptography.exceptions import InvalidTag

from app.crypto import decrypt, encrypt


@pytest.fixture(autouse=True)
def _fake_encryption_key(monkeypatch):
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    from app import config

    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_encrypt_decrypt_round_trip():
    ciphertext = encrypt("my-secret-bot-token")
    assert ciphertext != "my-secret-bot-token"
    assert decrypt(ciphertext) == "my-secret-bot-token"


def test_encrypt_produces_different_ciphertext_each_time():
    assert encrypt("same-token") != encrypt("same-token")


def test_decrypt_rejects_tampered_ciphertext():
    ciphertext = encrypt("my-secret-bot-token")
    tail = "AAAA" if not ciphertext.endswith("AAAA") else "BBBB"
    tampered = ciphertext[:-4] + tail
    with pytest.raises(InvalidTag):
        decrypt(tampered)

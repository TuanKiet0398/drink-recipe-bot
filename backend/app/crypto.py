import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

_NONCE_SIZE = 12


def _aesgcm() -> AESGCM:
    settings = get_settings()
    key = base64.b64decode(settings.encryption_key)
    return AESGCM(key)


def encrypt(plaintext: str) -> str:
    aesgcm = _aesgcm()
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt(ciphertext: str) -> str:
    aesgcm = _aesgcm()
    raw = base64.b64decode(ciphertext)
    nonce, encrypted = raw[:_NONCE_SIZE], raw[_NONCE_SIZE:]
    return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")

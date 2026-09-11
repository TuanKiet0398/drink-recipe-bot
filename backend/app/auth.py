import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import get_db
from app.db.models import Account, AdminAuditLog

security = HTTPBasic()

_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT_PARAMS)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT_PARAMS)
        return secrets.compare_digest(digest, bytes.fromhex(digest_hex))
    except (AttributeError, TypeError, ValueError):
        return False


def _is_env_admin(username: str, password: str) -> bool:
    settings = get_settings()
    correct_username = secrets.compare_digest(username, settings.admin_username)
    correct_password = secrets.compare_digest(password, settings.admin_password)
    return correct_username and correct_password


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """Any signed-in account: the .env admin or a registered web account.
    Every account has full panel access (no roles)."""
    if _is_env_admin(credentials.username, credentials.password):
        return credentials.username

    account = db.query(Account).filter_by(username=credentials.username).one_or_none()
    if account is not None and verify_password(credentials.password, account.password_hash):
        return credentials.username

    # Never log the attempted password — only the attempted username,
    # so failed logins are visible in the audit log without leaking
    # credential guesses into it.
    log_admin_action(
        db,
        action="login_failed",
        target=credentials.username,
        ip=request.client.host if request.client else "",
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid admin credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def log_admin_action(db: Session, action: str, target: str = "", ip: str = "") -> None:
    db.add(
        AdminAuditLog(
            action=action,
            target=target,
            ip=ip,
            created_at=datetime.now(UTC),
        )
    )
    db.commit()

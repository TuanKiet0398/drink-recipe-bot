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


def _authenticate(request: Request, credentials: HTTPBasicCredentials, db: Session) -> tuple[str, str]:
    """Verifies credentials against the .env admin or a registered web
    account. Returns (username, role) — the .env admin's role is always
    "admin"; a registered account's role is whatever `Account.role` says."""
    if _is_env_admin(credentials.username, credentials.password):
        return credentials.username, "admin"

    account = db.query(Account).filter_by(username=credentials.username).one_or_none()
    if account is not None and verify_password(credentials.password, account.password_hash):
        return credentials.username, account.role

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
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_account(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """Any signed-in account, customer or admin — for endpoints every
    signed-in user may use (chat)."""
    username, _role = _authenticate(request, credentials, db)
    return username


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    """A signed-in account with `role == "admin"` — the .env admin or an
    `Account` explicitly promoted to admin. A self-registered account is
    always "customer" and never reaches this: there is no public path to
    admin access."""
    username, role = _authenticate(request, credentials, db)
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return username


def require_account_with_role(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> tuple[str, str]:
    """Same as `require_account`, but also returns the role — for the login
    endpoint, which has to tell the frontend which role it signed in as."""
    return _authenticate(request, credentials, db)


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

import secrets
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import get_db
from app.db.models import AdminAuditLog

security = HTTPBasic()


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> str:
    settings = get_settings()
    correct_username = secrets.compare_digest(credentials.username, settings.admin_username)
    correct_password = secrets.compare_digest(credentials.password, settings.admin_password)
    if not (correct_username and correct_password):
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
    return credentials.username


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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.auth import require_admin
from app.db.base import get_db
from app.db.models import AdminAuditLog, Message

router = APIRouter(prefix="/admin/logs")


@router.get("/access")
def access_log(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(Message)
        .options(joinedload(Message.user))
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": m.id,
            "telegram_user_id": m.user.telegram_user_id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in rows
    ]


@router.get("/audit")
def audit_log(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    rows = (
        db.query(AdminAuditLog)
        .order_by(AdminAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "action": a.action,
            "target": a.target,
            "ip": a.ip,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]

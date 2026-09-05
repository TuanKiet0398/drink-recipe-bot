from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.auth import log_admin_action, require_admin
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


@router.delete("/audit/{entry_id}", status_code=204)
def delete_audit_log_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    entry = db.query(AdminAuditLog).filter_by(id=entry_id).one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    db.delete(entry)
    db.commit()

    log_admin_action(
        db, action="delete_audit_log", target=str(entry_id), ip=request.client.host if request.client else ""
    )


@router.delete("/audit", status_code=204)
def clear_audit_log(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    db.query(AdminAuditLog).delete()
    db.commit()

    # Logged after the delete, so this action's own entry is the only
    # survivor — a visible record that the log was cleared, and by whom.
    log_admin_action(db, action="clear_audit_log", ip=request.client.host if request.client else "")

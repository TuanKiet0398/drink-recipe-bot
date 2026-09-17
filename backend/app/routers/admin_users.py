from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import log_admin_action, require_account_with_role, require_admin
from app.db.base import get_db
from app.db.models import (
    ConversationSummary,
    CustomerNote,
    Favourite,
    Message,
    RecommendationHistory,
    TokenUsage,
    User,
)

router = APIRouter(prefix="/admin/users")

login_router = APIRouter(prefix="/admin")


@login_router.post("/login")
def login(
    request: Request,
    db: Session = Depends(get_db),
    account: tuple[str, str] = Depends(require_account_with_role),
):
    username, role = account
    log_admin_action(db, action="login", target=username, ip=request.client.host if request.client else "")
    return {"status": "ok", "role": role}


@router.get("")
def list_users(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    users = db.query(User).order_by(User.first_seen.desc()).all()
    result = []
    for u in users:
        message_count = db.query(func.count(Message.id)).filter(Message.user_id == u.id).scalar()
        favourites = [f.drink_name for f in db.query(Favourite).filter_by(user_id=u.id).all()]
        result.append(
            {
                "id": u.id,
                "channel_id": u.channel_id,
                "telegram_user_id": u.telegram_user_id,
                "first_seen": u.first_seen.isoformat(),
                "message_count": message_count,
                "favourites": favourites,
                "blocked": u.blocked,
            }
        )
    return result


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter_by(id=user_id).one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/block")
def block_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.blocked = True
    db.commit()
    log_admin_action(
        db,
        action="block_user",
        target=user.telegram_user_id,
        ip=request.client.host if request.client else "",
    )
    return {"id": user.id, "blocked": user.blocked}


@router.post("/{user_id}/unblock")
def unblock_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    user = _get_user_or_404(db, user_id)
    user.blocked = False
    db.commit()
    log_admin_action(
        db,
        action="unblock_user",
        target=user.telegram_user_id,
        ip=request.client.host if request.client else "",
    )
    return {"id": user.id, "blocked": user.blocked}


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    """Permanently erases one customer and every piece of memory tied to
    them. No soft-delete/undo — this is a hard delete, mirroring the force
    branch of `delete_channel` but scoped to a single user."""
    user = _get_user_or_404(db, user_id)
    target = user.telegram_user_id

    db.query(Message).filter_by(user_id=user_id).delete(synchronize_session="fetch")
    db.query(Favourite).filter_by(user_id=user_id).delete(synchronize_session="fetch")
    db.query(TokenUsage).filter_by(user_id=user_id).delete(synchronize_session="fetch")
    db.query(CustomerNote).filter_by(user_id=user_id).delete(synchronize_session="fetch")
    db.query(ConversationSummary).filter_by(user_id=user_id).delete(synchronize_session="fetch")
    db.query(RecommendationHistory).filter_by(user_id=user_id).delete(synchronize_session="fetch")
    db.delete(user)
    db.commit()

    log_admin_action(
        db, action="delete_user", target=target, ip=request.client.host if request.client else ""
    )

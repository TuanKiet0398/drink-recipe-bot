from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import log_admin_action, require_admin
from app.db.base import get_db
from app.db.models import Favourite, Message, User

router = APIRouter(prefix="/admin/users")

login_router = APIRouter(prefix="/admin")


@login_router.post("/login")
def login(
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    log_admin_action(db, action="login", target=admin_user, ip=request.client.host if request.client else "")
    return {"status": "ok"}


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
    log_admin_action(db, action="block_user", target=user.telegram_user_id, ip=request.client.host if request.client else "")
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
    log_admin_action(db, action="unblock_user", target=user.telegram_user_id, ip=request.client.host if request.client else "")
    return {"id": user.id, "blocked": user.blocked}

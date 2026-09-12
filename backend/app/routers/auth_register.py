from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, log_admin_action
from app.config import get_settings
from app.db.base import get_db
from app.db.models import Account
from app.routers.admin_chat import get_web_user

router = APIRouter(prefix="/auth")


class RegisterPayload(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    # The upper bound keeps a huge body from turning one request into a long scrypt run.
    password: str = Field(min_length=8, max_length=256)


@router.post("/register", status_code=201)
def register(payload: RegisterPayload, request: Request, db: Session = Depends(get_db)):
    taken = HTTPException(status_code=409, detail="Username already taken")
    # The .env admin has no account row, so its name is reserved explicitly.
    if payload.username == get_settings().admin_username:
        raise taken
    if db.query(Account).filter_by(username=payload.username).one_or_none() is not None:
        raise taken

    db.add(Account(username=payload.username, password_hash=hash_password(payload.password)))
    try:
        db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent registration
        db.rollback()
        raise taken from exc

    log_admin_action(
        db,
        action="account.register",
        target=payload.username,
        ip=request.client.host if request.client else "",
    )
    # Create the chat User eagerly so the account shows up on the Users page
    # right away, instead of only after its first chat message.
    get_web_user(db, payload.username)
    return {"username": payload.username}

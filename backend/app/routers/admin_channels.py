import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import log_admin_action, require_admin
from app.channel_manager import channel_manager
from app.crypto import decrypt, encrypt
from app.db.base import get_db
from app.db.models import Channel, Favourite, Message, TokenUsage, User
from app.telegram_client import get_me

router = APIRouter(prefix="/admin/channels")

ALLOWED_CHANNEL_TYPES = ("telegram",)


class ChannelCreate(BaseModel):
    key: str
    display_name: str
    channel_type: str
    bot_token: str


class ChannelTest(BaseModel):
    channel_type: str
    bot_token: str


class ChannelUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    bot_token: str | None = None


def _serialize(channel: Channel) -> dict:
    return {
        "id": channel.id,
        "key": channel.key,
        "display_name": channel.display_name,
        "channel_type": channel.channel_type,
        "is_active": channel.is_active,
        "created_at": channel.created_at.isoformat(),
    }


def _get_channel_or_404(db: Session, channel_id: int) -> Channel:
    channel = db.query(Channel).filter_by(id=channel_id).one_or_none()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.post("", status_code=201)
async def create_channel(
    payload: ChannelCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    if payload.channel_type not in ALLOWED_CHANNEL_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported channel_type: {payload.channel_type}")

    channel = Channel(
        key=payload.key,
        display_name=payload.display_name,
        channel_type=payload.channel_type,
        encrypted_credentials=encrypt(json.dumps({"bot_token": payload.bot_token})),
        is_active=True,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    log_admin_action(db, action="create_channel", target=channel.key, ip=request.client.host if request.client else "")
    await channel_manager.sync(db)

    return _serialize(channel)


@router.post("/test")
async def test_connection(
    payload: ChannelTest,
    admin_user: str = Depends(require_admin),
):
    if payload.channel_type not in ALLOWED_CHANNEL_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported channel_type: {payload.channel_type}")

    try:
        info = await get_me(payload.bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True, "username": info.get("username")}


@router.get("")
def list_channels(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    channels = db.query(Channel).order_by(Channel.created_at.desc()).all()
    return [_serialize(c) for c in channels]


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: int,
    payload: ChannelUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    channel = _get_channel_or_404(db, channel_id)

    if payload.display_name is not None:
        channel.display_name = payload.display_name
    if payload.is_active is not None:
        channel.is_active = payload.is_active
    if payload.bot_token is not None:
        channel.encrypted_credentials = encrypt(json.dumps({"bot_token": payload.bot_token}))

    db.commit()
    db.refresh(channel)

    log_admin_action(db, action="update_channel", target=channel.key, ip=request.client.host if request.client else "")
    await channel_manager.sync(db)

    return _serialize(channel)


@router.post("/{channel_id}/test")
async def test_existing_channel_connection(
    channel_id: int,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    channel = _get_channel_or_404(db, channel_id)
    bot_token = json.loads(decrypt(channel.encrypted_credentials))["bot_token"]

    try:
        info = await get_me(bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"ok": True, "username": info.get("username")}


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: int,
    request: Request,
    force: bool = False,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    channel = _get_channel_or_404(db, channel_id)
    key = channel.key

    user_ids = [u.id for u in db.query(User.id).filter_by(channel_id=channel_id).all()]
    if user_ids and not force:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {len(user_ids)} user(s) still belong to this channel. "
            "Deactivate it instead, or delete with force to also erase their chat history.",
        )

    if user_ids:
        # Deletes the users' conversation history permanently — only reached
        # when the admin explicitly opted into ?force=true after being
        # warned by the 409 above.
        db.query(Message).filter(Message.user_id.in_(user_ids)).delete(synchronize_session="fetch")
        db.query(Favourite).filter(Favourite.user_id.in_(user_ids)).delete(synchronize_session="fetch")
        db.query(TokenUsage).filter(TokenUsage.user_id.in_(user_ids)).delete(synchronize_session="fetch")
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session="fetch")

    db.delete(channel)
    db.commit()

    log_admin_action(db, action="delete_channel", target=key, ip=request.client.host if request.client else "")
    await channel_manager.sync(db)

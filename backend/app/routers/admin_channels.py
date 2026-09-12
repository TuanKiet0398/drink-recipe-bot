import hashlib
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import log_admin_action, require_admin
from app.channel_manager import channel_manager
from app.crypto import decrypt, encrypt
from app.db.base import get_db
from app.db.models import (
    Channel,
    ConversationSummary,
    CustomerNote,
    Favourite,
    Message,
    RecommendationHistory,
    TokenUsage,
    User,
)
from app.telegram_client import get_me


def _token_hash(bot_token: str) -> str:
    return hashlib.sha256(bot_token.encode("utf-8")).hexdigest()

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
    channel = db.query(Channel).filter_by(id=channel_id, deleted_at=None).one_or_none()
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

    token_hash = _token_hash(payload.bot_token)
    revived = (
        db.query(Channel)
        .filter(Channel.token_hash == token_hash, Channel.deleted_at.is_not(None))
        .one_or_none()
    )

    if revived is not None:
        revived.key = payload.key
        revived.display_name = payload.display_name
        revived.channel_type = payload.channel_type
        revived.encrypted_credentials = encrypt(json.dumps({"bot_token": payload.bot_token}))
        revived.is_active = True
        revived.deleted_at = None
        channel = revived
    else:
        channel = Channel(
            key=payload.key,
            display_name=payload.display_name,
            channel_type=payload.channel_type,
            encrypted_credentials=encrypt(json.dumps({"bot_token": payload.bot_token})),
            is_active=True,
            token_hash=token_hash,
        )
        db.add(channel)

    db.commit()
    db.refresh(channel)

    log_admin_action(
        db, action="create_channel", target=channel.key, ip=request.client.host if request.client else ""
    )
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
    # The "web" channel backs in-panel chat accounts; it is not editable here.
    channels = (
        db.query(Channel)
        .filter(Channel.channel_type != "web", Channel.deleted_at.is_(None))
        .order_by(Channel.created_at.desc())
        .all()
    )
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

    log_admin_action(
        db, action="update_channel", target=channel.key, ip=request.client.host if request.client else ""
    )
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

    if force:
        user_ids = [u.id for u in db.query(User.id).filter_by(channel_id=channel_id).all()]
        if user_ids:
            db.query(Message).filter(Message.user_id.in_(user_ids)).delete(synchronize_session="fetch")
            db.query(Favourite).filter(Favourite.user_id.in_(user_ids)).delete(synchronize_session="fetch")
            db.query(TokenUsage).filter(TokenUsage.user_id.in_(user_ids)).delete(synchronize_session="fetch")
            db.query(CustomerNote).filter(CustomerNote.user_id.in_(user_ids)).delete(
                synchronize_session="fetch"
            )
            db.query(ConversationSummary).filter(ConversationSummary.user_id.in_(user_ids)).delete(
                synchronize_session="fetch"
            )
            db.query(RecommendationHistory).filter(RecommendationHistory.user_id.in_(user_ids)).delete(
                synchronize_session="fetch"
            )
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session="fetch")
        db.delete(channel)
    else:
        # Soft delete: keep the channel row, its users and their memory, so
        # re-adding the same bot (matched by token_hash) revives everything.
        channel.deleted_at = datetime.now(UTC)
        channel.is_active = False

    db.commit()

    log_admin_action(
        db, action="delete_channel", target=key, ip=request.client.host if request.client else ""
    )
    await channel_manager.sync(db)

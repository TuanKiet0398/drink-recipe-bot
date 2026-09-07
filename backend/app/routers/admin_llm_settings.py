import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import llm_settings
from app.agent.clients import build_chat_client, invalidate_chat_client
from app.auth import log_admin_action, require_admin
from app.db.base import get_db

router = APIRouter(prefix="/admin/llm-settings")

_TEST_MAX_TOKENS = 5
_ERROR_MAX_CHARS = 200


class SettingsPayload(BaseModel):
    provider: str
    chat_model: str
    base_url: str | None = None
    # None means "keep whatever is stored"; the UI never sends the saved key back.
    api_key: str | None = None


def _validate(payload: SettingsPayload) -> None:
    if payload.provider not in llm_settings.PROVIDERS:
        raise HTTPException(status_code=400, detail=f"provider must be one of {llm_settings.PROVIDERS}")
    if not payload.chat_model.strip():
        raise HTTPException(status_code=400, detail="chat_model must not be empty")
    if payload.provider == "ollama":
        if not (payload.base_url or "").strip():
            raise HTTPException(status_code=400, detail="base_url is required for ollama")
        if not payload.base_url.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="base_url must start with http:// or https://")


def _key_for(payload: SettingsPayload, db: Session) -> str:
    """The key to use right now: the supplied one, else whatever is stored."""
    if payload.api_key:
        return payload.api_key
    return llm_settings.resolve(db).api_key


@router.get("")
def read_settings(db: Session = Depends(get_db), admin_user: str = Depends(require_admin)):
    resolved = llm_settings.resolve(db)
    row = llm_settings.read_row(db)
    return {
        "provider": resolved.provider,
        "base_url": resolved.base_url,
        "chat_model": resolved.chat_model,
        # The key itself is never serialised, in any form.
        "has_api_key": bool(resolved.api_key),
        "is_default": resolved.is_default,
        "updated_at": row.updated_at.isoformat() if row else None,
        "updated_by": row.updated_by if row else None,
    }


@router.post("/test")
def test_settings(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    """Try an unsaved configuration with one cheap call.

    Three deliberate choices: a throwaway client, so a broken configuration
    cannot disturb the one serving customers; no retry_once, so a failure is
    reported immediately and llm_retries_total stays clean; and no
    token_usage row, because this is an administrator's call, not a
    customer's.
    """
    _validate(payload)

    client = build_chat_client(payload.provider, payload.base_url, _key_for(payload, db))
    started = time.monotonic()
    try:
        client.chat.completions.create(
            model=payload.chat_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=_TEST_MAX_TOKENS,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:_ERROR_MAX_CHARS]}

    return {
        "ok": True,
        "model": payload.chat_model,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }


@router.post("/models")
def list_models(
    payload: SettingsPayload,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    """List the models the given (possibly unsaved) configuration exposes.

    Ollama serves /v1/models over its OpenAI-compatible endpoint, so one code
    path covers both providers. Same three rules as /test: a throwaway
    client, no retry_once, and no token_usage row.
    """
    _validate(payload)

    client = build_chat_client(payload.provider, payload.base_url, _key_for(payload, db))
    try:
        models = sorted(model.id for model in client.models.list())
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:_ERROR_MAX_CHARS], "models": [], "count": 0}

    return {"ok": True, "models": models, "count": len(models)}


@router.put("")
def update_settings(
    payload: SettingsPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    _validate(payload)

    llm_settings.save(
        db,
        provider=payload.provider,
        base_url=payload.base_url,
        api_key=payload.api_key,
        chat_model=payload.chat_model.strip(),
        updated_by=admin_user,
    )
    invalidate_chat_client()

    log_admin_action(
        db,
        action="llm_settings.update",
        # No api_key here, in any form — this record is readable in the UI.
        target=f"{payload.provider} {payload.base_url or ''} {payload.chat_model}".strip(),
        ip=request.client.host if request.client else "",
    )

    return read_settings(db=db, admin_user=admin_user)

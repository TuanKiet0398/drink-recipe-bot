"""Reading and writing the active LLM chat configuration.

This module owns the fallback rule: with no row in `llm_settings`, the
system behaves exactly as it did before the table existed — the chat client
is built from OPENAI_API_KEY with the default model.

Embeddings are not configurable here. See `app.agent.clients`.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import get_settings
from app.crypto import decrypt, encrypt
from app.db.models import LLMSettings

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
PROVIDERS = ("openai", "ollama")

_SINGLETON_ID = 1


@dataclass(frozen=True)
class ResolvedSettings:
    provider: str
    base_url: str | None
    api_key: str
    chat_model: str
    is_default: bool
    daily_token_limit: int | None


def read_row(db: Session) -> LLMSettings | None:
    return db.query(LLMSettings).filter_by(id=_SINGLETON_ID).one_or_none()


def resolve(db: Session) -> ResolvedSettings:
    row = read_row(db)
    if row is None:
        return ResolvedSettings(
            provider="openai",
            base_url=None,
            api_key=get_settings().openai_api_key,
            chat_model=DEFAULT_CHAT_MODEL,
            is_default=True,
            daily_token_limit=None,
        )
    return ResolvedSettings(
        provider=row.provider,
        base_url=row.base_url,
        api_key=decrypt(row.encrypted_api_key) if row.encrypted_api_key else "",
        chat_model=row.chat_model,
        is_default=False,
        daily_token_limit=row.daily_token_limit,
    )


def save(
    db: Session,
    provider: str,
    base_url: str | None,
    api_key: str | None,
    chat_model: str,
    updated_by: str,
    daily_token_limit: int | None = None,
) -> LLMSettings:
    """Upsert the singleton row.

    `api_key=None` means "leave the stored key alone", which is how the UI
    lets an admin change the model without re-entering the key.
    `daily_token_limit=None` means "no per-customer daily cap".
    """
    row = read_row(db)
    if row is None:
        row = LLMSettings(id=_SINGLETON_ID, provider=provider, chat_model=chat_model)
        db.add(row)

    row.provider = provider
    row.base_url = base_url
    row.chat_model = chat_model
    row.updated_by = updated_by
    row.daily_token_limit = daily_token_limit
    if api_key is not None:
        row.encrypted_api_key = encrypt(api_key) if api_key else None

    db.commit()
    db.refresh(row)
    return row

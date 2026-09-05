import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import TokenUsage

logger = logging.getLogger(__name__)


def log_token_usage(db: Session, user_id: int | None, call_type: str, model: str, usage) -> None:
    """Persist one OpenAI call's token usage. Never raises.

    `usage` is the OpenAI SDK's response `.usage` object (or `None`, in
    which case this is a no-op). Any failure — a malformed `usage` object,
    a DB error — is logged and swallowed, with the session rolled back so
    it stays usable for the rest of the request.
    """
    if usage is None:
        return
    try:
        completion_tokens = getattr(usage, "completion_tokens", None)
        db.add(
            TokenUsage(
                user_id=user_id,
                call_type=call_type,
                model=model,
                prompt_tokens=int(usage.prompt_tokens),
                completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
                total_tokens=int(usage.total_tokens),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to log token usage for call_type=%s model=%s", call_type, model)
        db.rollback()

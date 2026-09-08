import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Message, User

logger = logging.getLogger(__name__)

_SCAN_INTERVAL_SECONDS = 86400


def purge_inactive_messages(db: Session, inactive_days: int = 30) -> int:
    """Deletes raw `Message` rows for users whose `last_active_at` is more
    than `inactive_days` in the past. Never touches `User`,
    `ConversationSummary`, or `CustomerNote` rows — only the raw transcript
    is considered disposable. A user with `last_active_at IS NULL` (not yet
    set) is never eligible. Returns the number of `Message` rows deleted."""
    cutoff = datetime.now(UTC) - timedelta(days=inactive_days)
    inactive_user_ids = (
        db.execute(
            select(User.id).where(User.last_active_at.is_not(None), User.last_active_at < cutoff)
        )
        .scalars()
        .all()
    )
    if not inactive_user_ids:
        return 0

    messages = (
        db.execute(select(Message).where(Message.user_id.in_(inactive_user_ids))).scalars().all()
    )
    count = len(messages)
    for message in messages:
        db.delete(message)
    db.commit()
    return count

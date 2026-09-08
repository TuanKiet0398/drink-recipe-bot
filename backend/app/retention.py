import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
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


async def run_retention_loop(interval_seconds: int = _SCAN_INTERVAL_SECONDS) -> None:
    """Runs `purge_inactive_messages` on a fixed schedule for the lifetime
    of the process, following the same shape as `run_poller()` in
    `app/telegram_poller.py`: cancellation propagates immediately, any
    other failure is logged and the loop continues on the next
    interval."""
    logger.info("30-day message retention loop started")
    while True:
        db = SessionLocal()
        try:
            deleted = purge_inactive_messages(db)
            if deleted:
                logger.info("Retention purge deleted %s message(s)", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Retention purge failed; retrying next interval")
        finally:
            db.close()
        await asyncio.sleep(interval_seconds)

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_once(fn: Callable[[], T], delay_seconds: float = 0.5) -> T:
    """Call `fn`, retrying exactly once (after a short delay) on failure.

    If both attempts raise, the exception from the retry is propagated so
    callers (e.g. the webhook handler) can fall back to the friendly error
    reply.
    """
    try:
        return fn()
    except Exception:
        time.sleep(delay_seconds)
        return fn()

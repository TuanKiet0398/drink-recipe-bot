import time
from typing import Callable, TypeVar

from app.metrics import record_llm_call, record_retry

T = TypeVar("T")


def retry_once(
    fn: Callable[[], T],
    delay_seconds: float = 0.5,
    call_type: str = "unknown",
    model: str = "unknown",
) -> T:
    """Call `fn`, retrying exactly once (after a short delay) on failure.

    If both attempts raise, the exception from the retry is propagated so
    callers (e.g. the webhook handler) can fall back to the friendly error
    reply.

    `call_type` and `model` only label metrics; they never affect control
    flow, and both default so existing call sites keep working.
    """
    try:
        return fn()
    except Exception:
        record_retry(call_type)
        time.sleep(delay_seconds)
        try:
            return fn()
        except Exception:
            record_llm_call(model, call_type, "error")
            raise

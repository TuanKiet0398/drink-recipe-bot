import logging
import os
from functools import lru_cache
from pathlib import Path

from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.rails.llm.options import GenerationResponse

from app.config import get_settings
from app.metrics import record_guardrail_outcome

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent


@lru_cache
def _rails() -> LLMRails:
    # NeMo Guardrails' OpenAI client reads OPENAI_API_KEY from the process
    # environment directly (standard openai SDK lookup) rather than through
    # this app's pydantic Settings, so the key has to be exported here
    # before the rail's LLM client is constructed.
    os.environ.setdefault("OPENAI_API_KEY", get_settings().openai_api_key)
    return LLMRails(RailsConfig.from_path(str(_CONFIG_DIR)))


def check_grounded(question: str, reply: str, relevant_chunks: list[str]) -> str:
    """Runs the NeMo Guardrails `self check facts` output rail against an
    already-generated `reply`, using `relevant_chunks` as evidence.

    Returns `reply` unchanged when the rail allows it (nothing to check, or
    the LLM judged it grounded), or the rail's refusal message when it
    doesn't. Fails open — a guardrail-side error (network, config, LLM
    outage) returns the original `reply` rather than blocking the bot,
    matching how every other LLM-dependent step in this agent degrades.
    """
    if not reply.strip() or not relevant_chunks:
        record_guardrail_outcome("skipped")
        return reply

    messages = [
        {
            "role": "context",
            "content": {"relevant_chunks": "\n".join(relevant_chunks), "check_facts": True},
        },
        {"role": "user", "content": question},
        {"role": "assistant", "content": reply},
    ]

    try:
        result = _rails().generate(messages=messages, options={"rails": {"dialog": False}})
    except Exception:
        logger.exception("self_check_facts rail failed; returning the ungated reply")
        record_guardrail_outcome("error")
        return reply

    # When the rail allows the reply, it echoes `reply` back unchanged (older
    # NeMo Guardrails versions instead returned empty content for an allow —
    # both are treated as "allowed" here). Any other content is the rail's
    # own refusal utterance.
    content = ""
    if isinstance(result, GenerationResponse) and isinstance(result.response, list) and result.response:
        content = result.response[0].get("content") or ""
    content = content.strip()
    if not content or content == reply.strip():
        record_guardrail_outcome("allowed")
        return reply
    record_guardrail_outcome("refused")
    return content

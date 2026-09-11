import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.agent.clients import get_chat_client, get_chat_model, get_chroma_client, get_embedding_client
from app.agent.nodes import generate, retrieve
from app.agent.state import AgentState
from app.auth import require_admin
from app.db.base import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/chat")

# Same window fetch_history loads for a real customer.
HISTORY_LIMIT = 10


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatPayload(BaseModel):
    message: str = Field(max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value


def _run(state: AgentState, db: Session) -> tuple[str, str]:
    chat_client = get_chat_client(db)
    chat_model = get_chat_model(db)
    retrieve(state, db, get_chroma_client(), chat_client, get_embedding_client(), chat_model)
    generate(state, db, chat_client, chat_model)
    return state.reply, chat_model


@router.post("")
async def chat(
    payload: ChatPayload,
    db: Session = Depends(get_db),
    admin_user: str = Depends(require_admin),
):
    """Lets an admin test the bot's replies without a real customer.

    Stateless: the client sends the conversation so far. It skips
    fetch_history (per-customer memory) and the background extractors, and
    writes no User/Message rows — only token usage, with user_id=None."""
    state = AgentState(
        user_id=None,
        chat_id="admin-chat",
        incoming_text=payload.message,
        history=[turn.model_dump() for turn in payload.history[-HISTORY_LIMIT:]],
    )
    try:
        # retrieve/generate make blocking LLM calls; keep them off the event loop.
        reply, model = await asyncio.to_thread(_run, state, db)
    except Exception as exc:
        logger.exception("admin test chat failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"reply": reply, "model": model}

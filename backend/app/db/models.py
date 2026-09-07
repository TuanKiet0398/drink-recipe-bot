from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String)
    channel_type: Mapped[str] = mapped_column(String)
    encrypted_credentials: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="channel")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_channel_id_telegram_user_id", "channel_id", "telegram_user_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    telegram_user_id: Mapped[str] = mapped_column(String)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    channel: Mapped["Channel"] = relationship(back_populates="users")
    messages: Mapped[list["Message"]] = relationship(back_populates="user")
    favourites: Mapped[list["Favourite"]] = relationship(back_populates="user")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="messages")


class Favourite(Base):
    __tablename__ = "favourites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    drink_name: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String, default="inferred")
    source: Mapped[str] = mapped_column(String, default="chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    user: Mapped["User"] = relationship(back_populates="favourites")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String)
    chunk_count: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String, default="")
    ip: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    call_type: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class LLMSettings(Base):
    """Singleton row (id is always 1) holding the active chat provider.

    Embeddings are deliberately not represented here: the Chroma index is
    built with OpenAI's text-embedding-3-small, so changing that provider
    would invalidate every stored vector.
    """

    __tablename__ = "llm_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_llm_settings_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String)
    base_url: Mapped[str | None] = mapped_column(String, nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(String, nullable=True)
    chat_model: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    updated_by: Mapped[str] = mapped_column(String, default="")

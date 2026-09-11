from pydantic import BaseModel, Field


class AgentState(BaseModel):
    # None for the admin test chat, which has no customer behind it.
    user_id: int | None
    chat_id: str
    incoming_text: str
    history: list[dict] = Field(default_factory=list)
    favourites: list[str] = Field(default_factory=list)
    summary: str | None = None
    customer_notes: dict[str, str] = Field(default_factory=dict)
    recommendation_history: list[str] = Field(default_factory=list)
    retrieved_chunks: list[str] = Field(default_factory=list)
    reply: str = ""

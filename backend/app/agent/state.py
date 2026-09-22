from pydantic import BaseModel, Field


class AgentState(BaseModel):
    user_id: int
    chat_id: str
    incoming_text: str
    history: list[dict] = Field(default_factory=list)
    favourites: list[str] = Field(default_factory=list)
    summary: str | None = None
    customer_notes: dict[str, str] = Field(default_factory=dict)
    recommendation_history: list[str] = Field(default_factory=list)
    retrieved_chunks: list[str] = Field(default_factory=list)
    # Parallel to retrieved_chunks (same order, same length) — source
    # metadata for citation display. retrieved_chunks stays plain text so
    # existing consumers (check_facts, extract_recommendation, generate)
    # need no changes.
    retrieved_sources: list[dict] = Field(default_factory=list)
    reply: str = ""

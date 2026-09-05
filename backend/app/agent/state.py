from pydantic import BaseModel, Field


class AgentState(BaseModel):
    user_id: int
    chat_id: str
    incoming_text: str
    history: list[dict] = Field(default_factory=list)
    favourites: list[str] = Field(default_factory=list)
    retrieved_chunks: list[str] = Field(default_factory=list)
    reply: str = ""

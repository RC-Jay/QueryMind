import json
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Any


# ── Requests ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ConfirmRequest(BaseModel):
    approved: bool


# ── Internal transport ────────────────────────────────────────────────────────

class SSEEvent(BaseModel):
    """An event streamed to the client over the SSE connection."""
    event: str
    data: Any


# ── Responses (built via .model_validate(orm_obj)) ────────────────────────────

class ConversationSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    created_at: datetime | None = None  # Pydantic serializes to ISO 8601
    updated_at: datetime | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _default_title(cls, v):
        return v or "New conversation"


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    role: str
    content: dict
    created_at: datetime | None = None

    @field_validator("content", mode="before")
    @classmethod
    def _parse_content(cls, v):
        # messages.content is stored as a JSON string; accept either.
        return json.loads(v) if isinstance(v, str) else v


class ConversationDetailOut(BaseModel):
    id: str
    title: str
    messages: list[MessageOut]

    @field_validator("title", mode="before")
    @classmethod
    def _default_title(cls, v):
        return v or "New conversation"

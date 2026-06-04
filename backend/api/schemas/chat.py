from pydantic import BaseModel
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


# ── Responses ─────────────────────────────────────────────────────────────────

class ConversationSummaryOut(BaseModel):
    id: str
    title: str
    created_at: str | None = None
    updated_at: str | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: dict
    created_at: str | None = None


class ConversationDetailOut(BaseModel):
    id: str
    title: str
    messages: list[MessageOut]

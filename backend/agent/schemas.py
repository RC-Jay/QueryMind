from pydantic import BaseModel
from typing import Any


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class SSEEvent(BaseModel):
    event: str
    data: Any


class ConfirmRequest(BaseModel):
    approved: bool

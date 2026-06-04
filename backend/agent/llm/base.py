"""
Provider-agnostic LLM abstraction (Strategy pattern).

The orchestrator depends only on the LLMProvider protocol and these normalized
types — never on a vendor SDK. To add a new provider (Gemini, Anthropic, a
local model), implement LLMProvider and register it in factory.py. No
orchestrator or tool code changes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, AsyncIterator, runtime_checkable


@dataclass
class ToolCall:
    """A normalized tool/function call requested by the model."""
    id: str
    name: str
    arguments: str  # raw JSON string, parsed by the tool registry


@dataclass
class LLMResponse:
    """A normalized, SDK-neutral completion result."""
    finish_reason: str                       # "tool_calls" | "stop"
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


@runtime_checkable
class LLMProvider(Protocol):
    """Strategy interface every model backend must implement."""

    async def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        """One non-streaming completion. Used during the tool-calling phase."""
        ...

    def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[str]:
        """Stream the final answer token-by-token (no further tool calls)."""
        ...

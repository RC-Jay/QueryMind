"""
Anthropic Claude implementation of the LLMProvider strategy.

The orchestrator speaks an OpenAI-shaped message/tool dialect and the normalized
LLMResponse/ToolCall types. Claude's Messages API differs (system is a top-level
param; tool calls/results are content blocks), so this provider translates in
both directions. The orchestrator is unaware of any of it.
"""
from __future__ import annotations
import json
from typing import AsyncIterator
from anthropic import AsyncAnthropic
from agent.llm.base import LLMResponse, ToolCall

DEFAULT_MAX_TOKENS = 4096


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Pull the system prompt out; Anthropic takes it as a separate param."""
    system_parts = [m["content"] for m in messages if m["role"] == "system" and m.get("content")]
    rest = [m for m in messages if m["role"] != "system"]
    return "\n\n".join(system_parts), rest


def _to_anthropic_messages(messages: list[dict]) -> list[dict]:
    """Translate OpenAI-shaped messages → Anthropic content-block messages.

    Consecutive tool results are merged into a single user message, as Anthropic
    requires all tool_result blocks for one assistant turn in the next user turn.
    """
    out: list[dict] = []
    for m in messages:
        role = m["role"]
        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": m["tool_call_id"],
                "content": m.get("content") or "",
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(block)  # merge into the running user turn
            else:
                out.append({"role": "user", "content": [block]})
        elif role == "assistant" and m.get("tool_calls"):
            blocks = [
                {
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": json.loads(tc["function"]["arguments"] or "{}"),
                }
                for tc in m["tool_calls"]
            ]
            out.append({"role": "assistant", "content": blocks})
        else:
            out.append({"role": role, "content": m.get("content") or ""})
    return out


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """OpenAI function tools → Anthropic tool schema."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
        }
        for t in tools
    ]


class ClaudeProvider:
    def __init__(self, api_key: str, model: str, temperature: float = 0.1,
                 max_tokens: int = DEFAULT_MAX_TOKENS):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    async def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        system, conv = _split_system(messages)
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system or None,
            messages=_to_anthropic_messages(conv),
            tools=_to_anthropic_tools(tools),
        )
        tool_calls = [
            ToolCall(id=block.id, name=block.name, arguments=json.dumps(block.input))
            for block in resp.content
            if block.type == "tool_use"
        ]
        text = "".join(block.text for block in resp.content if block.type == "text") or None
        finish = "tool_calls" if resp.stop_reason == "tool_use" else "stop"
        return LLMResponse(finish_reason=finish, text=text, tool_calls=tool_calls)

    async def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[str]:
        system, conv = _split_system(messages)
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=system or None,
            messages=_to_anthropic_messages(conv),
        ) as stream:
            async for text in stream.text_stream:
                if text:
                    yield text

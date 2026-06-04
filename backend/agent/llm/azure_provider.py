"""Azure OpenAI implementation of the LLMProvider strategy."""
from __future__ import annotations
from typing import AsyncIterator
from openai import AsyncAzureOpenAI
from agent.llm.base import LLMResponse, ToolCall


class AzureOpenAIProvider:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        api_version: str,
        deployment: str,
        temperature: float = 0.1,
    ):
        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self._deployment = deployment
        self._temperature = temperature

    async def complete(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        resp = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            stream=False,
            temperature=self._temperature,
        )
        choice = resp.choices[0]
        msg = choice.message
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
            for tc in (msg.tool_calls or [])
        ]
        return LLMResponse(
            finish_reason=choice.finish_reason or "stop",
            text=msg.content,
            tool_calls=tool_calls,
        )

    async def stream(self, messages: list[dict], tools: list[dict]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            tools=tools,
            tool_choice="none",
            stream=True,
            temperature=self._temperature,
        )
        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta

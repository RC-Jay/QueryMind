import json
import asyncio
from typing import Callable, Awaitable, AsyncIterator
from openai import AzureOpenAI
from openai import AsyncAzureOpenAI
from tools.registry import ToolRegistry
from tools.schema_tool import GetSchemaTool
from tools.query_tool import ExecuteQueryTool
from tools.chart_tool import GenerateChartTool
from tools.kpi_tool import GetKPISnapshotTool
from agent.prompt import build_system_prompt
from db.analytics import BusinessConfig
from config import get_settings


def _tool_result_message(tool_call_id: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }


class AgentOrchestrator:
    """
    Template Method pattern: run() defines the loop.
    Strategy pattern: tools injected via ToolRegistry.
    """

    MAX_TOOL_ROUNDS = 8  # safety cap to prevent infinite loops

    def __init__(self, config: BusinessConfig):
        self._config = config
        self._settings = get_settings()
        self._client = AsyncAzureOpenAI(
            azure_endpoint=self._settings.azure_openai_endpoint,
            api_key=self._settings.azure_openai_api_key,
            api_version=self._settings.azure_openai_api_version,
        )
        self._registry = ToolRegistry()
        kpi_defs = json.loads(config.kpi_definitions) if isinstance(config.kpi_definitions, str) else config.kpi_definitions
        self._registry.register(GetSchemaTool())
        self._registry.register(ExecuteQueryTool(cost_threshold=config.explain_cost_threshold))
        self._registry.register(GenerateChartTool())
        self._registry.register(GetKPISnapshotTool(kpi_definitions=kpi_defs))

    async def run(
        self,
        history: list[dict],
        user_message: str,
        send_event: Callable[[dict], Awaitable[None]],
    ) -> str:
        """
        Run the agent loop. Calls send_event for each SSE event.
        Returns the final assistant text response.
        """
        system_prompt = build_system_prompt(self._config)
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": user_message},
        ]

        final_text = ""

        for _ in range(self.MAX_TOOL_ROUNDS):
            response = await self._client.chat.completions.create(
                model=self._settings.azure_openai_deployment,
                messages=messages,
                tools=self._registry.get_openai_definitions(),
                tool_choice="auto",
                stream=False,
                temperature=0.1,
            )
            choice = response.choices[0]

            if choice.finish_reason == "tool_calls":
                messages.append(choice.message.model_dump())
                for tool_call in choice.message.tool_calls:
                    result = await self._registry.dispatch(tool_call, send_event)
                    # Emit SSE event for rich output (chart/table/metrics)
                    if result.sse_event:
                        await send_event(result.sse_event)
                    # Build tool result content for the next LLM call
                    if result.cancelled:
                        content = f"Tool call was not completed: {result.reason}"
                    elif result.type == "table":
                        content = json.dumps(result.data)
                    else:
                        content = json.dumps(result.data) if result.data is not None else "Done"
                    messages.append(_tool_result_message(tool_call.id, content))

            elif choice.finish_reason in ("stop", "length", None):
                # Switch to streaming for the final text response
                messages.append({"role": "user", "content": ""})  # placeholder removed below
                messages.pop()

                stream = await self._client.chat.completions.create(
                    model=self._settings.azure_openai_deployment,
                    messages=messages,
                    tools=self._registry.get_openai_definitions(),
                    tool_choice="none",  # no more tool calls on final pass
                    stream=True,
                    temperature=0.1,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content or "" if chunk.choices else ""
                    if delta:
                        final_text += delta
                        await send_event({"event": "text_delta", "data": {"delta": delta}})

                await send_event({"event": "done", "data": {}})
                break

        return final_text

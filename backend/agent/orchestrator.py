import json
from typing import Callable, Awaitable
from tools.registry import ToolRegistry
from tools.schema_tool import GetSchemaTool
from tools.query_tool import ExecuteQueryTool
from tools.chart_tool import GenerateChartTool
from tools.kpi_tool import GetKPISnapshotTool
from agent.prompt import build_system_prompt
from agent.llm.base import LLMProvider, ToolCall
from db.analytics import BusinessConfig
from services.confirmation import InMemoryConfirmationBroker


def _tool_result_message(tool_call_id: str, content: str) -> dict:
    return {"role": "tool", "tool_call_id": tool_call_id, "content": content}


def _assistant_tool_calls_message(tool_calls: list[ToolCall]) -> dict:
    """Reconstruct the assistant message (OpenAI wire shape) from normalized calls."""
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
            for tc in tool_calls
        ],
    }


class AgentOrchestrator:
    """
    Template Method: run() defines the tool-use loop.
    Strategy: the LLM backend (LLMProvider) and the tools (ToolRegistry) are
    injected — no vendor SDK or DB client is referenced here directly.
    """

    MAX_TOOL_ROUNDS = 8  # safety cap against infinite tool loops

    def __init__(self, config: BusinessConfig, llm: LLMProvider, registry: ToolRegistry):
        self._config = config
        self._llm = llm
        self._registry = registry
        self.audit_entries: list = []  # AuditEntry per SQL execution this run

    @classmethod
    def build(cls, config: BusinessConfig, llm: LLMProvider, pool, broker=None) -> "AgentOrchestrator":
        """Wire the standard toolset with an injected DB pool and confirmation broker."""
        broker = broker or InMemoryConfirmationBroker()
        registry = ToolRegistry()
        kpi_defs = config.kpi_definitions  # JSON column → already a list
        registry.register(GetSchemaTool(pool))
        registry.register(ExecuteQueryTool(pool, broker, cost_threshold=config.explain_cost_threshold))
        registry.register(GenerateChartTool())
        registry.register(GetKPISnapshotTool(pool, kpi_definitions=kpi_defs))
        return cls(config, llm, registry)

    async def run(
        self,
        history: list[dict],
        user_message: str,
        send_event: Callable[[dict], Awaitable[None]],
    ) -> str:
        """Run the agent loop, emitting SSE events. Returns the final text."""
        messages = [
            {"role": "system", "content": build_system_prompt(self._config)},
            *history,
            {"role": "user", "content": user_message},
        ]
        tools = self._registry.get_openai_definitions()
        final_text = ""

        for _ in range(self.MAX_TOOL_ROUNDS):
            response = await self._llm.complete(messages, tools)

            if response.finish_reason == "tool_calls":
                messages.append(_assistant_tool_calls_message(response.tool_calls))
                for tool_call in response.tool_calls:
                    result = await self._registry.dispatch(tool_call, send_event)
                    if result.audit is not None:
                        self.audit_entries.append(result.audit)
                    if result.sse_event:
                        await send_event(result.sse_event)
                    if result.cancelled:
                        content = f"Tool call was not completed: {result.reason}"
                    elif result.data is not None:
                        content = json.dumps(result.data)
                    else:
                        content = "Done"
                    messages.append(_tool_result_message(tool_call.id, content))
            else:
                # Final answer — stream tokens
                async for delta in self._llm.stream(messages, tools):
                    final_text += delta
                    await send_event({"event": "text_delta", "data": {"delta": delta}})
                await send_event({"event": "done", "data": {}})
                break

        return final_text

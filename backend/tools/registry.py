import json
from tools.base import BaseTool, ToolResult
from agent.llm.base import ToolCall
from typing import Callable, Awaitable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get_openai_definitions(self) -> list[dict]:
        return [t.openai_definition() for t in self._tools.values()]

    async def dispatch(
        self,
        tool_call: ToolCall,
        send_event: Callable[[dict], Awaitable[None]],
    ) -> ToolResult:
        tool = self._tools.get(tool_call.name)
        if tool is None:
            return ToolResult(type="text", data=f"Unknown tool: {tool_call.name}", cancelled=True)
        try:
            kwargs = json.loads(tool_call.arguments or "{}")
            return await tool.execute(send_event=send_event, **kwargs)
        except Exception as exc:
            return ToolResult(type="text", cancelled=True, reason=str(exc))

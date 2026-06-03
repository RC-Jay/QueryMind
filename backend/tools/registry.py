import json
from tools.base import BaseTool, ToolResult
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
        tool_call,
        send_event: Callable[[dict], Awaitable[None]],
    ) -> ToolResult:
        name = tool_call.function.name
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(type="text", data=f"Unknown tool: {name}", cancelled=True)
        try:
            kwargs = json.loads(tool_call.function.arguments or "{}")
            return await tool.execute(send_event=send_event, **kwargs)
        except Exception as exc:
            return ToolResult(type="text", cancelled=True, reason=str(exc))

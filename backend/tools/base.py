from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolResult:
    type: str                        # "chart" | "table" | "metrics" | "text" | "cancelled"
    data: Any = None
    source: str = ""
    cancelled: bool = False
    reason: str = ""
    sse_event: dict | None = None    # populated by tool after constructing result


class BaseTool(ABC):
    name: str
    description: str
    parameters_schema: dict

    def openai_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }

    @abstractmethod
    async def execute(self, send_event: Callable[[dict], Awaitable[None]], **kwargs) -> ToolResult:
        ...

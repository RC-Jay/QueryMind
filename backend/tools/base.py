from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class AuditEntry:
    """A record of one SQL execution attempt, for the audit log."""
    sql: str
    outcome: str               # "executed" | "blocked" | "cancelled" | "failed"
    rows_returned: int | None = None
    duration_ms: int | None = None


@dataclass
class ToolResult:
    type: str                        # "chart" | "table" | "metrics" | "text" | "cancelled"
    data: Any = None
    source: str = ""
    cancelled: bool = False
    reason: str = ""
    sse_event: dict | None = None    # populated by tool after constructing result
    audit: AuditEntry | None = None  # set by tools that run user SQL


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

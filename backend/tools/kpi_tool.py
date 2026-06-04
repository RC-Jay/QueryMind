from tools.base import BaseTool, ToolResult
from services.kpi_service import compute_kpis
from typing import Callable, Awaitable


class GetKPISnapshotTool(BaseTool):
    name = "get_kpi_snapshot"
    description = (
        "Get a real-time snapshot of the top business KPIs. "
        "Use for 'how are we doing today/right now' type questions."
    )
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    def __init__(self, pool, kpi_definitions: list[dict]):
        self._pool = pool
        self._kpi_definitions = kpi_definitions

    async def execute(self, send_event: Callable[[dict], Awaitable[None]]) -> ToolResult:
        items = await compute_kpis(self._pool, self._kpi_definitions)
        result = ToolResult(type="metrics", data=items, source="Live business data")
        result.sse_event = {"event": "metrics", "data": {"items": items}}
        return result

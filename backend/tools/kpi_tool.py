import json
from tools.base import BaseTool, ToolResult
from db.business_db import get_pool
from typing import Callable, Awaitable


def _format_value(value, fmt: str) -> str:
    if value is None:
        return "N/A"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)

    if fmt == "currency":
        return f"₹{num:,.0f}" if num >= 1 else f"₹{num:.2f}"
    elif fmt == "percent":
        return f"{num:.1f}%"
    elif fmt == "number":
        return f"{int(num):,}"
    elif fmt == "decimal":
        return f"{num:.2f}"
    return str(value)


class GetKPISnapshotTool(BaseTool):
    name = "get_kpi_snapshot"
    description = (
        "Get a real-time snapshot of the top business KPIs. "
        "Use for 'how are we doing today/right now' type questions."
    )
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    def __init__(self, kpi_definitions: list[dict]):
        self._kpi_definitions = kpi_definitions

    async def execute(self, send_event: Callable[[dict], Awaitable[None]]) -> ToolResult:
        pool = await get_pool()
        results = []
        async with pool.acquire() as conn:
            for kpi in self._kpi_definitions:
                try:
                    value = await conn.fetchval(kpi["sql"])
                    formatted = _format_value(value, kpi.get("format", "number"))
                except Exception as exc:
                    formatted = "Error"
                results.append({
                    "label": kpi["name"],
                    "value": formatted,
                    "icon": kpi.get("icon", ""),
                })

        result = ToolResult(type="metrics", data=results, source="Live business data")
        result.sse_event = {"event": "metrics", "data": {"items": results}}
        return result

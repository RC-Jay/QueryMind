import asyncio
import re
import time
import json
from uuid import uuid4
from typing import Callable, Awaitable
from tools.base import BaseTool, ToolResult
from db.business_db import get_pool
from db.safety import validate_sql

# Shared dict of pending confirmations: query_id → (event, approved_flag)
_pending: dict[str, tuple[asyncio.Event, list]] = {}


def register_pending(query_id: str) -> tuple[asyncio.Event, list]:
    event = asyncio.Event()
    flag = [None]  # flag[0] = True/False when resolved
    _pending[query_id] = (event, flag)
    return event, flag


def resolve_pending(query_id: str, approved: bool) -> bool:
    entry = _pending.get(query_id)
    if entry is None:
        return False
    event, flag = entry
    flag[0] = approved
    event.set()
    return True


def _parse_explain_cost(plan_line: str) -> float:
    match = re.search(r"cost=[\d.]+\.\.([\d.]+)", plan_line)
    return float(match.group(1)) if match else 0.0


class ExecuteQueryTool(BaseTool):
    name = "execute_query"
    description = (
        "Execute a read-only SQL SELECT query against the business database. "
        "Returns up to 1000 rows. Provide a description of what the query retrieves for source attribution."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "A valid PostgreSQL SELECT statement"},
            "description": {"type": "string", "description": "One sentence describing what this query retrieves"},
        },
        "required": ["sql", "description"],
    }

    def __init__(self, cost_threshold: int = 50_000):
        self.cost_threshold = cost_threshold

    async def execute(
        self,
        send_event: Callable[[dict], Awaitable[None]],
        sql: str,
        description: str = "",
    ) -> ToolResult:
        # 1. Safety validation
        validation = validate_sql(sql)
        if not validation.ok:
            return ToolResult(type="text", cancelled=True, reason=f"Query blocked: {validation.reason}")

        pool = await get_pool()
        async with pool.acquire() as conn:
            # 2. EXPLAIN to estimate cost
            try:
                explain_rows = await conn.fetch(f"EXPLAIN {sql}")
                cost = _parse_explain_cost(str(explain_rows[0][0])) if explain_rows else 0.0
            except Exception:
                cost = 0.0

            # 3. Expensive query gate
            if cost > self.cost_threshold:
                query_id = str(uuid4())
                event, flag = register_pending(query_id)
                await send_event({
                    "event": "confirmation_required",
                    "data": {
                        "query_id": query_id,
                        "estimated_cost": cost,
                        "warning": (
                            "This query is estimated to be expensive and may impact "
                            "platform performance during peak hours. Do you want to proceed?"
                        ),
                    },
                })
                try:
                    await asyncio.wait_for(event.wait(), timeout=30.0)
                except asyncio.TimeoutError:
                    _pending.pop(query_id, None)
                    await send_event({"event": "confirmation_cancelled", "data": {"query_id": query_id}})
                    return ToolResult(type="text", cancelled=True, reason="Query cancelled — no response within 30 seconds.")

                _pending.pop(query_id, None)
                if not flag[0]:
                    return ToolResult(type="text", cancelled=True, reason="Query cancelled by user.")

            # 4. Execute with statement timeout
            start = time.monotonic()
            try:
                await conn.execute("SET statement_timeout = '10000'")
                rows = await conn.fetch(sql)
            except Exception as exc:
                return ToolResult(type="text", cancelled=True, reason=f"Query failed: {exc}")
            duration_ms = int((time.monotonic() - start) * 1000)

        if not rows:
            return ToolResult(type="table", data={"columns": [], "rows": [], "total": 0}, source=description)

        columns = list(rows[0].keys())
        data_rows = [[str(v) if v is not None else None for v in row.values()] for row in rows[:1000]]

        result = ToolResult(
            type="table",
            data={"columns": columns, "rows": data_rows, "total": len(rows)},
            source=description,
        )
        result.sse_event = {
            "event": "table",
            "data": {"columns": columns, "rows": data_rows, "total": len(rows), "source": description},
        }
        return result

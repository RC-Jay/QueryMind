import asyncio
import re
import time
from uuid import uuid4
from typing import Callable, Awaitable
from tools.base import BaseTool, ToolResult, AuditEntry
from db.safety import validate_sql
from services.confirmation import ConfirmationBroker


def _materialize_rows(rows) -> tuple[list, list]:
    """Stringify up to 1000 result rows. CPU-bound (O(rows × cols)) — offloaded."""
    columns = list(rows[0].keys())
    data_rows = [[str(v) if v is not None else None for v in row.values()] for row in rows[:1000]]
    return columns, data_rows


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

    def __init__(self, pool, broker: ConfirmationBroker, cost_threshold: int = 50_000):
        self._pool = pool
        self._broker = broker
        self.cost_threshold = cost_threshold

    async def execute(
        self,
        send_event: Callable[[dict], Awaitable[None]],
        sql: str,
        description: str = "",
    ) -> ToolResult:
        # 1. Safety validation — record blocked attempts (governance-relevant)
        validation = validate_sql(sql)
        if not validation.ok:
            return ToolResult(
                type="text", cancelled=True, reason=f"Query blocked: {validation.reason}",
                audit=AuditEntry(sql=sql, outcome="blocked"),
            )

        # 2. EXPLAIN to estimate cost (short-lived connection, released immediately)
        cost = await self._estimate_cost(sql)

        # 3. Expensive query gate. Crucially, NO DB connection is held while we
        #    wait on the human — otherwise pending confirmations would exhaust
        #    the pool under concurrency.
        if cost > self.cost_threshold:
            approved = await self._await_confirmation(send_event, cost)
            if not approved:
                reason = (
                    "Query cancelled — no response within 30 seconds."
                    if approved is None else "Query cancelled by user."
                )
                return ToolResult(
                    type="text", cancelled=True, reason=reason,
                    audit=AuditEntry(sql=sql, outcome="cancelled"),
                )

        # 4. Execute on a fresh connection with a server-side statement timeout
        start = time.monotonic()
        try:
            rows = await self._run_query(sql)
        except Exception as exc:
            return ToolResult(
                type="text", cancelled=True, reason=f"Query failed: {exc}",
                audit=AuditEntry(sql=sql, outcome="failed"),
            )
        duration_ms = int((time.monotonic() - start) * 1000)

        audit = AuditEntry(sql=sql, outcome="executed", rows_returned=len(rows), duration_ms=duration_ms)

        if not rows:
            return ToolResult(
                type="table", data={"columns": [], "rows": [], "total": 0},
                source=description, audit=audit,
            )

        columns, data_rows = await asyncio.to_thread(_materialize_rows, rows)

        result = ToolResult(
            type="table",
            data={"columns": columns, "rows": data_rows, "total": len(rows)},
            source=description,
            audit=audit,
        )
        result.sse_event = {
            "event": "table",
            "data": {"columns": columns, "rows": data_rows, "total": len(rows), "source": description},
        }
        return result

    async def _estimate_cost(self, sql: str) -> float:
        """Run EXPLAIN on a short-lived connection and parse the upper cost bound."""
        try:
            async with self._pool.acquire() as conn:
                explain_rows = await conn.fetch(f"EXPLAIN {sql}")
            return _parse_explain_cost(str(explain_rows[0][0])) if explain_rows else 0.0
        except Exception:
            return 0.0

    async def _await_confirmation(
        self, send_event: Callable[[dict], Awaitable[None]], cost: float
    ) -> bool | None:
        """
        Ask the user to confirm an expensive query. Holds NO DB connection while
        waiting. Returns True (approved), False (denied), or None (timed out).
        """
        query_id = str(uuid4())
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
        approved = await self._broker.wait(query_id, timeout=30.0)
        if approved is None:
            await send_event({"event": "confirmation_cancelled", "data": {"query_id": query_id}})
        return approved

    async def _run_query(self, sql: str) -> list:
        """Execute the SELECT on a fresh connection with a server-side timeout."""
        async with self._pool.acquire() as conn:
            await conn.execute("SET statement_timeout = '10000'")
            return await conn.fetch(sql)

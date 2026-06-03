import json
from tools.base import BaseTool, ToolResult
from db.business_db import get_pool
from typing import Callable, Awaitable


class GetSchemaTool(BaseTool):
    name = "get_schema"
    description = (
        "Get column names and data types for specified database tables. "
        "Call this before writing a query for a table you haven't seen yet."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "table_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of table names to inspect",
            }
        },
        "required": ["table_names"],
    }

    async def execute(self, send_event: Callable[[dict], Awaitable[None]], table_names: list[str]) -> ToolResult:
        pool = await get_pool()
        schema_info = {}
        async with pool.acquire() as conn:
            for table in table_names:
                rows = await conn.fetch(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table,
                )
                if rows:
                    schema_info[table] = [
                        {"column": r["column_name"], "type": r["data_type"], "nullable": r["is_nullable"] == "YES"}
                        for r in rows
                    ]
                else:
                    schema_info[table] = None  # table not found

        result_text = json.dumps(schema_info, indent=2)
        return ToolResult(type="text", data=result_text)

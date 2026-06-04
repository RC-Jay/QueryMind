import json
import asyncio
import pytest
from tools.schema_tool import GetSchemaTool
from tools.query_tool import ExecuteQueryTool
from tools.chart_tool import GenerateChartTool
from tools.kpi_tool import GetKPISnapshotTool
from services.confirmation import InMemoryConfirmationBroker
from tests.conftest import FakeConn, FakePool


async def _noop_send(event):
    pass


# ── schema tool ───────────────────────────────────────────────────────────────

async def test_schema_tool_returns_columns():
    conn = FakeConn(rows=[
        {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
        {"column_name": "name", "data_type": "text", "is_nullable": "YES"},
    ])
    tool = GetSchemaTool(FakePool(conn))
    result = await tool.execute(_noop_send, table_names=["business_business"])
    payload = json.loads(result.data)
    assert payload["business_business"][0]["column"] == "id"
    assert payload["business_business"][1]["nullable"] is True


# ── query tool ────────────────────────────────────────────────────────────────

async def test_query_tool_blocks_unsafe_sql():
    tool = ExecuteQueryTool(FakePool(FakeConn()), InMemoryConfirmationBroker(), cost_threshold=50000)
    result = await tool.execute(_noop_send, sql="DROP TABLE users", description="x")
    assert result.cancelled
    assert "blocked" in result.reason.lower()


async def test_query_tool_returns_table_for_cheap_query():
    conn = FakeConn(rows=[{"campus": "IIT", "revenue": 1000}], explain_cost=10.0)
    tool = ExecuteQueryTool(FakePool(conn), InMemoryConfirmationBroker(), cost_threshold=50000)
    result = await tool.execute(_noop_send, sql="SELECT campus, revenue FROM order_order", description="rev")
    assert result.type == "table"
    assert result.data["columns"] == ["campus", "revenue"]
    assert result.data["total"] == 1
    assert "SET statement_timeout = '10000'" in conn.executed


async def test_query_tool_expensive_query_requires_confirmation_then_proceeds():
    conn = FakeConn(rows=[{"x": 1}], explain_cost=999999.0)
    broker = InMemoryConfirmationBroker()
    tool = ExecuteQueryTool(FakePool(conn), broker, cost_threshold=50000)

    events = []
    async def capture(event):
        events.append(event)

    task = asyncio.create_task(tool.execute(capture, sql="SELECT x FROM big", description="d"))
    await asyncio.sleep(0.05)

    conf = next(e for e in events if e["event"] == "confirmation_required")
    assert conf["data"]["estimated_cost"] > 50000
    await broker.signal(conf["data"]["query_id"], approved=True)

    result = await task
    assert result.type == "table"


class CountingPool:
    """FakePool that tracks concurrent connection checkouts."""

    def __init__(self, conn):
        self._conn = conn
        self.active = 0
        self.max_active = 0

    def acquire(self):
        pool, conn = self, self._conn

        class _Ctx:
            async def __aenter__(self):
                pool.active += 1
                pool.max_active = max(pool.max_active, pool.active)
                return conn

            async def __aexit__(self, *exc):
                pool.active -= 1
                return False

        return _Ctx()


async def test_no_connection_held_during_confirmation_wait():
    """Regression: the expensive-query gate must NOT hold a pooled connection
    while waiting on the user, or pending confirmations would exhaust the pool."""
    conn = FakeConn(rows=[{"x": 1}], explain_cost=999999.0)
    pool = CountingPool(conn)
    broker = InMemoryConfirmationBroker()
    tool = ExecuteQueryTool(pool, broker, cost_threshold=50000)

    events = []
    async def capture(event):
        events.append(event)

    task = asyncio.create_task(tool.execute(capture, sql="SELECT x FROM big", description="d"))
    await asyncio.sleep(0.05)  # now parked on the confirmation wait

    assert pool.active == 0, "a DB connection is being held during the human wait"

    conf = next(e for e in events if e["event"] == "confirmation_required")
    await broker.signal(conf["data"]["query_id"], approved=True)
    result = await task

    assert result.type == "table"
    assert pool.max_active == 1  # EXPLAIN and execute never overlapped


async def test_query_tool_expensive_query_denied():
    conn = FakeConn(rows=[{"x": 1}], explain_cost=999999.0)
    broker = InMemoryConfirmationBroker()
    tool = ExecuteQueryTool(FakePool(conn), broker, cost_threshold=50000)

    events = []
    async def capture(event):
        events.append(event)

    task = asyncio.create_task(tool.execute(capture, sql="SELECT x FROM big", description="d"))
    await asyncio.sleep(0.05)
    conf = next(e for e in events if e["event"] == "confirmation_required")
    await broker.signal(conf["data"]["query_id"], approved=False)

    result = await task
    assert result.cancelled
    assert "cancelled by user" in result.reason.lower()


# ── chart tool ────────────────────────────────────────────────────────────────

async def test_chart_tool_builds_plotly_json():
    tool = GenerateChartTool()
    data = {"columns": ["campus", "revenue"], "rows": [["IIT", "100"], ["COEP", "80"]]}
    result = await tool.execute(
        _noop_send, data=data, chart_type="bar", title="Rev", x_column="campus", y_column="revenue"
    )
    assert result.type == "chart"
    assert result.sse_event["event"] == "chart"
    assert result.data["data"][0]["type"] == "bar"


async def test_chart_tool_rejects_missing_column():
    tool = GenerateChartTool()
    data = {"columns": ["a"], "rows": [["1"]]}
    result = await tool.execute(
        _noop_send, data=data, chart_type="bar", title="x", x_column="a", y_column="missing"
    )
    assert result.cancelled


# ── kpi tool ──────────────────────────────────────────────────────────────────

async def test_kpi_tool_formats_values():
    conn = FakeConn(fetchval_value=124200)
    tool = GetKPISnapshotTool(FakePool(conn), kpi_definitions=[
        {"name": "Today's GMV", "sql": "SELECT 1", "format": "currency", "icon": "rupee"},
    ])
    result = await tool.execute(_noop_send)
    assert result.type == "metrics"
    assert result.data[0]["label"] == "Today's GMV"
    assert result.data[0]["value"] == "₹124,200"
    assert result.sse_event["event"] == "metrics"

import pytest
from sqlalchemy import select, func
from db.analytics import AuditLog
from services.audit_service import record_queries
from tools.base import AuditEntry
from tools.query_tool import ExecuteQueryTool
from services.confirmation import InMemoryConfirmationBroker
from tests.conftest import FakeConn, FakePool


async def _noop_send(event):
    pass


# ── audit_service ─────────────────────────────────────────────────────────────

async def test_record_queries_writes_rows(analytics_session):
    entries = [
        AuditEntry(sql="SELECT 1", outcome="executed", rows_returned=5, duration_ms=12),
        AuditEntry(sql="DROP TABLE x", outcome="blocked"),
    ]
    await record_queries(analytics_session, user_id=1, conversation_id="c1",
                         question="how many?", entries=entries)

    rows = (await analytics_session.execute(select(AuditLog))).scalars().all()
    assert len(rows) == 2
    by_outcome = {r.outcome: r for r in rows}
    assert by_outcome["executed"].rows_returned == 5
    assert by_outcome["executed"].duration_ms == 12
    assert by_outcome["executed"].user_id == 1
    assert by_outcome["executed"].question == "how many?"
    assert by_outcome["blocked"].sql_executed == "DROP TABLE x"


async def test_record_queries_empty_is_noop(analytics_session):
    await record_queries(analytics_session, 1, "c1", "q", entries=[])
    count = (await analytics_session.execute(select(func.count()).select_from(AuditLog))).scalar()
    assert count == 0


# ── ExecuteQueryTool populates .audit on every path ───────────────────────────

async def test_audit_executed():
    conn = FakeConn(rows=[{"a": 1}], explain_cost=10.0)
    tool = ExecuteQueryTool(FakePool(conn), InMemoryConfirmationBroker(), cost_threshold=50000)
    result = await tool.execute(_noop_send, sql="SELECT a FROM t", description="d")
    assert result.audit.outcome == "executed"
    assert result.audit.rows_returned == 1
    assert result.audit.duration_ms is not None


async def test_audit_blocked():
    tool = ExecuteQueryTool(FakePool(FakeConn()), InMemoryConfirmationBroker(), cost_threshold=50000)
    result = await tool.execute(_noop_send, sql="DROP TABLE users", description="d")
    assert result.audit.outcome == "blocked"
    assert result.audit.sql == "DROP TABLE users"


async def test_audit_failed():
    conn = FakeConn(explain_cost=10.0, fetch_error=RuntimeError("boom"))
    tool = ExecuteQueryTool(FakePool(conn), InMemoryConfirmationBroker(), cost_threshold=50000)
    result = await tool.execute(_noop_send, sql="SELECT bad FROM t", description="d")
    assert result.audit.outcome == "failed"

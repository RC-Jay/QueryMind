import asyncio
import pytest
from services.kpi_service import compute_kpis


class _SqlKeyedConn:
    """Fake conn whose fetchval returns a per-SQL value (or raises)."""
    def __init__(self, values: dict):
        self._values = values

    async def fetchval(self, sql, *args):
        v = self._values[sql]
        if isinstance(v, Exception):
            raise v
        return v


class _MultiConnPool:
    """Hands out a connection per acquire; tracks max concurrent checkouts."""
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
                await asyncio.sleep(0)  # let other tasks check out too
                return conn

            async def __aexit__(self, *exc):
                pool.active -= 1
                return False

        return _Ctx()


async def test_compute_kpis_preserves_order_and_formats():
    defs = [
        {"name": "GMV", "sql": "q_gmv", "format": "currency", "icon": "rupee"},
        {"name": "Orders", "sql": "q_orders", "format": "number", "icon": "pkg"},
        {"name": "Rate", "sql": "q_rate", "format": "percent", "icon": "chk"},
    ]
    pool = _MultiConnPool(_SqlKeyedConn({"q_gmv": 124200, "q_orders": 1243, "q_rate": 87.3}))

    items = await compute_kpis(pool, defs)

    assert [i["label"] for i in items] == ["GMV", "Orders", "Rate"]   # order preserved
    assert items[0]["value"] == "₹124,200"
    assert items[1]["value"] == "1,243"
    assert items[2]["value"] == "87.3%"


async def test_compute_kpis_failing_query_is_na_not_fatal():
    defs = [
        {"name": "OK", "sql": "ok", "format": "number"},
        {"name": "Bad", "sql": "bad", "format": "number"},
    ]
    pool = _MultiConnPool(_SqlKeyedConn({"ok": 5, "bad": RuntimeError("boom")}))

    items = await compute_kpis(pool, defs)
    assert items[0]["value"] == "5"
    assert items[1]["value"] == "N/A"   # one failure doesn't sink the snapshot


async def test_compute_kpis_runs_concurrently():
    defs = [{"name": f"k{i}", "sql": f"q{i}", "format": "number"} for i in range(4)]
    pool = _MultiConnPool(_SqlKeyedConn({f"q{i}": i for i in range(4)}))

    await compute_kpis(pool, defs)
    assert pool.max_active > 1   # queries overlapped (not run one-by-one)

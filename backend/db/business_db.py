"""
asyncpg connection pool for the live business PostgreSQL DB.
The connection URL comes from business_config (decrypted at runtime) —
never from an environment variable.
"""
import time
import asyncpg
from dataclasses import dataclass
from typing import Optional

# How long a tool waits for a connection from the pool before giving up.
# Without this, pool.acquire() can hang indefinitely when the DB is down,
# leaving the user staring at a spinner for up to agent_run_timeout_seconds.
_ACQUIRE_TIMEOUT = 10.0  # seconds

# Health check settings.
# check_pool_health() does a SELECT 1 and caches the result for this long.
# Chat turns check health before calling the LLM — stale DBs are rejected
# immediately rather than wasting an LLM call that will fail anyway.
_HEALTH_CHECK_INTERVAL = 60.0   # seconds between real DB pings
_HEALTH_CHECK_TIMEOUT  =  3.0   # seconds to wait for SELECT 1 to respond


class _PoolWithAcquireTimeout:
    """Thin wrapper that enforces a per-acquire timeout on every pool.acquire() call.

    All tools do `async with pool.acquire() as conn` — this intercepts that
    call and injects the timeout so DB unreachability surfaces in ~10s rather
    than waiting for the 120s agent ceiling.
    """

    def __init__(self, pool: asyncpg.Pool, timeout: float):
        self._pool = pool
        self._timeout = timeout

    def acquire(self):
        return self._pool.acquire(timeout=self._timeout)

    def __getattr__(self, name):
        # Delegate everything else (close, fetchval, etc.) to the real pool.
        return getattr(self._pool, name)


_pool: Optional[_PoolWithAcquireTimeout] = None


# ── Cached health state ───────────────────────────────────────────────────────

@dataclass
class _HealthState:
    healthy: bool
    checked_at: float   # time.monotonic() timestamp


_health: Optional[_HealthState] = None


async def check_pool_health(*, force: bool = False) -> bool:
    """Return True if the business DB pool can serve a connection right now.

    The result is cached for _HEALTH_CHECK_INTERVAL seconds so chat turns
    only incur one real DB round-trip per minute, not one per message.

    Pass force=True to bypass the cache (e.g. after a pool reload).
    """
    global _health

    now = time.monotonic()

    # Return cached result if still fresh.
    if (
        not force
        and _health is not None
        and (now - _health.checked_at) < _HEALTH_CHECK_INTERVAL
    ):
        return _health.healthy

    if _pool is None:
        _health = _HealthState(healthy=False, checked_at=now)
        return False

    # Ping the DB with a short timeout — we just need a yes/no, not a full
    # acquire-timeout worth of waiting.
    try:
        async with _pool._pool.acquire(timeout=_HEALTH_CHECK_TIMEOUT) as conn:
            await conn.fetchval("SELECT 1")
        _health = _HealthState(healthy=True, checked_at=now)
        return True
    except Exception:
        _health = _HealthState(healthy=False, checked_at=now)
        return False


def invalidate_health_cache() -> None:
    """Force the next check_pool_health() call to re-ping the DB.
    Call this after reloading the pool so the new connection is tested."""
    global _health
    _health = None


# ── Pool lifecycle ─────────────────────────────────────────────────────────────

async def init_pool(db_url: str) -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
    raw = await asyncpg.create_pool(
        dsn=db_url,
        min_size=0,   # don't create connections at pool-creation time — avoids
                      # hanging on asyncpg.create_pool() when the DB is unreachable
        max_size=10,
        timeout=5,    # per-connection TCP timeout; fail fast if DB is unreachable
        command_timeout=12,
        max_inactive_connection_lifetime=60,  # recycle stale connections quickly
    )
    _pool = _PoolWithAcquireTimeout(raw, _ACQUIRE_TIMEOUT)
    invalidate_health_cache()


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Business DB pool not initialised. Configure the business connection via admin UI.")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def test_connection(db_url: str) -> tuple[bool, str]:
    """Open a single connection to validate the URL. Does not affect the live pool."""
    try:
        conn = await asyncpg.connect(dsn=db_url, timeout=5)
        await conn.fetchval("SELECT 1")
        await conn.close()
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)

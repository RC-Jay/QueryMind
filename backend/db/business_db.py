"""
asyncpg connection pool for the live business PostgreSQL DB.
The connection URL comes from business_config (decrypted at runtime) —
never from an environment variable.
"""
import asyncpg
from typing import Optional

_pool: Optional[asyncpg.Pool] = None


async def init_pool(db_url: str) -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
    _pool = await asyncpg.create_pool(
        dsn=db_url,
        min_size=2,
        max_size=10,
        command_timeout=12,
    )


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

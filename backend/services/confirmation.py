"""
Confirmation broker for the expensive-query gate.

The agent coroutine that's streaming a response parks until the user approves or
denies an expensive query. The approval arrives on a *separate* HTTP request
(`POST /api/chat/confirm/{id}`) which — behind multiple workers — may land on a
different process. So the wait/signal pair must communicate through shared state.

- RedisConfirmationBroker  — production. Uses a Redis list (RPUSH/BLPOP), which
  is race-free: the decision survives even if it arrives before the waiter blocks.
- InMemoryConfirmationBroker — single-process fallback (local dev, tests). Uses
  an asyncio.Event. Only correct within one process, which is exactly its scope.

Both satisfy ConfirmationBroker, so the tool and routes depend on the interface.
"""
from __future__ import annotations
import asyncio
from functools import lru_cache
from typing import Protocol

_KEY = "querymind:confirm:{}"
_TTL_SECONDS = 60


class ConfirmationBroker(Protocol):
    async def wait(self, query_id: str, timeout: float) -> bool | None:
        """Block until a decision arrives. True=approved, False=denied, None=timed out."""
        ...

    async def signal(self, query_id: str, approved: bool) -> bool:
        """Deliver a decision. Returns whether it was/will be received (best-effort)."""
        ...


class InMemoryConfirmationBroker:
    def __init__(self) -> None:
        self._pending: dict[str, tuple[asyncio.Event, list]] = {}

    async def wait(self, query_id: str, timeout: float) -> bool | None:
        event = asyncio.Event()
        flag: list = [None]
        self._pending[query_id] = (event, flag)
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._pending.pop(query_id, None)
        return bool(flag[0])

    async def signal(self, query_id: str, approved: bool) -> bool:
        entry = self._pending.get(query_id)
        if entry is None:
            return False
        event, flag = entry
        flag[0] = approved
        event.set()
        return True


class RedisConfirmationBroker:
    def __init__(self, client) -> None:
        self._redis = client

    async def wait(self, query_id: str, timeout: float) -> bool | None:
        # BLPOP blocks until an element is pushed, or the timeout elapses. If the
        # decision was pushed before we got here, it's already in the list — no race.
        res = await self._redis.blpop([_KEY.format(query_id)], timeout=int(timeout))
        if res is None:
            return None
        _, value = res
        return value == "1"

    async def signal(self, query_id: str, approved: bool) -> bool:
        key = _KEY.format(query_id)
        await self._redis.rpush(key, "1" if approved else "0")
        await self._redis.expire(key, _TTL_SECONDS)  # self-clean if never consumed
        return True


@lru_cache
def get_confirmation_broker() -> ConfirmationBroker:
    """Singleton: Redis broker when REDIS_URL is set, else in-process."""
    from config import get_settings
    if get_settings().redis_url:
        from db.redis_client import get_redis
        return RedisConfirmationBroker(get_redis())
    return InMemoryConfirmationBroker()

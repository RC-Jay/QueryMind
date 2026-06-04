import asyncio
from api.routes.chat import _acquire


async def test_acquires_when_slot_free():
    sem = asyncio.Semaphore(1)
    assert await _acquire(sem, timeout=0.1) is True


async def test_rejects_when_exhausted():
    sem = asyncio.Semaphore(1)
    assert await _acquire(sem, timeout=0.1) is True   # take the only slot
    assert await _acquire(sem, timeout=0.05) is False  # none left → shed


async def test_slot_reusable_after_release():
    sem = asyncio.Semaphore(1)
    await _acquire(sem, timeout=0.1)
    assert await _acquire(sem, timeout=0.05) is False
    sem.release()
    assert await _acquire(sem, timeout=0.1) is True    # freed slot is reusable


async def test_concurrency_cap_enforced():
    sem = asyncio.Semaphore(2)
    assert await _acquire(sem, timeout=0.1) is True
    assert await _acquire(sem, timeout=0.1) is True
    assert await _acquire(sem, timeout=0.05) is False   # 3rd blocked at cap of 2

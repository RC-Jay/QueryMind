import asyncio
from services.confirmation import InMemoryConfirmationBroker


async def test_signal_before_timeout_approves():
    broker = InMemoryConfirmationBroker()

    async def confirm_soon():
        await asyncio.sleep(0.02)
        delivered = await broker.signal("q1", approved=True)
        assert delivered is True

    asyncio.create_task(confirm_soon())
    result = await broker.wait("q1", timeout=1.0)
    assert result is True


async def test_denied():
    broker = InMemoryConfirmationBroker()

    async def deny_soon():
        await asyncio.sleep(0.02)
        await broker.signal("q2", approved=False)

    asyncio.create_task(deny_soon())
    result = await broker.wait("q2", timeout=1.0)
    assert result is False


async def test_timeout_returns_none():
    broker = InMemoryConfirmationBroker()
    result = await broker.wait("nobody", timeout=0.05)
    assert result is None


async def test_signal_unknown_query_returns_false():
    broker = InMemoryConfirmationBroker()
    # No one is waiting on this id
    assert await broker.signal("ghost", approved=True) is False

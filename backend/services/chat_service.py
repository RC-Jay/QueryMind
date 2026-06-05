"""
Chat turn orchestration — the application logic for one conversation turn.

Transport-free: takes primitives, raises domain exceptions, and yields neutral
event dicts ({event, data}). The HTTP layer (api/routes/chat.py) handles auth,
backpressure, and SSE wire-formatting.
"""
import asyncio
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from config import get_settings
from exceptions import NotFoundError
from services.business_config_service import get_config_or_raise
from services.llm_config_service import get_llm_config_or_raise
from services.confirmation import get_confirmation_broker
from services.audit_service import record_queries
from services.conversation_service import (
    create_conversation, get_conversation, append_message,
)
from services.history_service import get_history_strategy, TextOnlyExtractor
from agent.orchestrator import AgentOrchestrator
from agent.llm.factory import create_llm_provider


async def run_turn(
    session: AsyncSession,
    pool,
    *,
    user_id: int,
    message: str,
    conversation_id: str | None,
) -> AsyncIterator[dict]:
    """Run one chat turn. Eager setup (incl. NotFoundError) happens before the
    returned generator starts streaming, so a 404 surfaces before the SSE stream.
    Returns an async generator yielding event dicts."""
    settings = get_settings()
    config = await get_config_or_raise(session)

    if conversation_id:
        conv = await get_conversation(session, conversation_id, user_id)
        if not conv:
            raise NotFoundError("Conversation not found")
    else:
        # Title is set at creation time from the opening message — never updated.
        conv = await create_conversation(session, user_id, title=message[:80])

    # Build the LLM provider first — the history strategy may need it for
    # summarisation (SummarizedStrategy calls llm.complete on the pre-window set).
    llm = create_llm_provider(await get_llm_config_or_raise(session))

    # Build the context window for this turn.
    # history_result.cache_breakpoint is available for future prompt-caching
    # integration (e.g. mark messages[:cache_breakpoint] as stable prefix for
    # Claude/Azure caching) — no strategy changes needed when that lands.
    strategy = get_history_strategy(settings.history_summarize)
    history_result = await strategy.build(
        session, conv.id,
        max_turns=settings.history_turns,
        extractor=TextOnlyExtractor(),
        llm=llm,
    )

    await append_message(session, conv.id, "user", {"text": message})

    orchestrator = AgentOrchestrator.build(config, llm, pool, broker=get_confirmation_broker())

    event_queue: asyncio.Queue = asyncio.Queue()
    collected_text: list[str] = []

    async def send_event(event: dict):
        await event_queue.put(event)
        if event.get("event") == "text_delta":
            collected_text.append(event["data"].get("delta", ""))

    async def run_and_signal():
        try:
            await asyncio.wait_for(
                orchestrator.run(history_result.messages, message, send_event),
                timeout=settings.agent_run_timeout_seconds,
            )
        except (asyncio.TimeoutError, TimeoutError):
            await event_queue.put({"event": "error", "data": {"message": "The request took too long and was stopped."}})
        except Exception as exc:
            await event_queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await event_queue.put(None)  # sentinel

    asyncio.create_task(run_and_signal())

    async def generate() -> AsyncIterator[dict]:
        yield {"event": "conversation_id", "data": {"id": conv.id}}
        while True:
            event = await event_queue.get()
            if event is None:
                break
            yield event

        # Persist assistant reply + audit after the stream completes.
        full_text = "".join(collected_text)
        if full_text:
            await append_message(session, conv.id, "assistant", {"text": full_text})
        await record_queries(
            session, user_id=user_id, conversation_id=conv.id,
            question=message, entries=orchestrator.audit_entries,
        )

    return generate()

"""
Chat turn orchestration — the application logic for one conversation turn.

Transport-free: takes primitives, raises domain exceptions, and yields neutral
event dicts ({event, data}). The HTTP layer (api/routes/chat.py) handles auth,
backpressure, and SSE wire-formatting.
"""
import asyncio
import json
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from config import get_settings
from exceptions import NotFoundError
from services.business_config_service import get_config_or_raise
from services.llm_config_service import get_llm_config_or_raise
from services.confirmation import get_confirmation_broker
from services.audit_service import record_queries
from services.conversation_service import (
    create_conversation, get_conversation, append_message, get_messages, set_conversation_title,
)
from agent.orchestrator import AgentOrchestrator
from agent.llm.factory import create_llm_provider

HISTORY_TURNS = 20


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
    config = await get_config_or_raise(session)

    if conversation_id:
        conv = await get_conversation(session, conversation_id, user_id)
        if not conv:
            raise NotFoundError("Conversation not found")
    else:
        conv = await create_conversation(session, user_id)

    # Last N turns as plain text (context-replay of charts/tables is Phase 2).
    raw_messages = await get_messages(session, conv.id)
    history = [
        {"role": m.role, "content": json.loads(m.content).get("text", "")}
        for m in raw_messages[-HISTORY_TURNS:]
    ]

    await append_message(session, conv.id, "user", {"text": message})
    await set_conversation_title(session, conv.id, message[:80])

    llm = create_llm_provider(await get_llm_config_or_raise(session))
    orchestrator = AgentOrchestrator.build(config, llm, pool, broker=get_confirmation_broker())

    event_queue: asyncio.Queue = asyncio.Queue()
    collected_text: list[str] = []

    async def send_event(event: dict):
        await event_queue.put(event)
        if event.get("event") == "text_delta":
            collected_text.append(event["data"].get("delta", ""))

    run_timeout = get_settings().agent_run_timeout_seconds

    async def run_and_signal():
        try:
            await asyncio.wait_for(
                orchestrator.run(history, message, send_event), timeout=run_timeout
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

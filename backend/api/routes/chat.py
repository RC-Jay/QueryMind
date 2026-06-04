import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from db.analytics import get_session, User
from services.business_config_service import get_config_or_raise
from services.conversation_service import (
    create_conversation, get_conversation, list_conversations,
    delete_conversation, append_message, get_messages, set_conversation_title,
)
from agent.orchestrator import AgentOrchestrator
from agent.llm.factory import create_llm_provider
from services.llm_config_service import get_llm_config_or_raise
from api.schemas.chat import (
    ChatRequest, ConfirmRequest, ConversationSummaryOut, MessageOut, ConversationDetailOut,
)
from api.schemas.common import DetailResponse
from services.confirmation import get_confirmation_broker
from services.audit_service import record_queries
from api.deps import get_current_user, get_business_pool
from config import get_settings

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Backpressure: cap concurrent agent runs PER WORKER. Excess requests wait up to
# chat_acquire_timeout_seconds for a slot, then get a 429 (graceful shedding)
# rather than piling up unbounded coroutines/connections.
_chat_slots = asyncio.Semaphore(get_settings().max_concurrent_chats)


async def _acquire(sem: asyncio.Semaphore, timeout: float) -> bool:
    """Try to acquire a semaphore within `timeout`. Returns False if it can't."""
    try:
        await asyncio.wait_for(sem.acquire(), timeout=timeout)
        return True
    except (asyncio.TimeoutError, TimeoutError):
        return False


async def _acquire_chat_slot() -> bool:
    return await _acquire(_chat_slots, get_settings().chat_acquire_timeout_seconds)


async def _sse_stream(generator):
    async for event in generator:
        yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"


async def _run_agent(request: ChatRequest, current_user: User, session: AsyncSession, pool):
    config = await get_config_or_raise(session)

    # Resolve or create conversation
    if request.conversation_id:
        conv = await get_conversation(session, request.conversation_id, current_user.id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conv = await create_conversation(session, current_user.id)

    # Build message history for the agent (last 20 turns to keep context manageable)
    raw_messages = await get_messages(session, conv.id)
    history = []
    for m in raw_messages[-20:]:
        content_data = json.loads(m.content)
        history.append({"role": m.role, "content": content_data.get("text", "")})

    # Persist user message
    await append_message(session, conv.id, "user", {"text": request.message})
    await set_conversation_title(session, conv.id, request.message[:80])

    llm_config = await get_llm_config_or_raise(session)
    llm = create_llm_provider(llm_config)
    orchestrator = AgentOrchestrator.build(config, llm, pool, broker=get_confirmation_broker())

    event_queue: asyncio.Queue = asyncio.Queue()
    collected_text = []

    async def send_event(event: dict):
        await event_queue.put(event)
        if event.get("event") == "text_delta":
            collected_text.append(event["data"].get("delta", ""))

    run_timeout = get_settings().agent_run_timeout_seconds

    async def run_and_signal():
        try:
            await asyncio.wait_for(
                orchestrator.run(history, request.message, send_event),
                timeout=run_timeout,
            )
        except (asyncio.TimeoutError, TimeoutError):
            await event_queue.put({"event": "error", "data": {"message": "The request took too long and was stopped."}})
        except Exception as exc:
            await event_queue.put({"event": "error", "data": {"message": str(exc)}})
        finally:
            await event_queue.put(None)  # sentinel

    # Start agent in background, stream events to client
    task = asyncio.create_task(run_and_signal())

    async def generate():
        # Always send conversation_id first so frontend knows which conversation this is
        yield {"event": "conversation_id", "data": {"id": conv.id}}

        while True:
            event = await event_queue.get()
            if event is None:
                break
            yield event

        # Persist assistant response after streaming completes
        full_text = "".join(collected_text)
        if full_text:
            await append_message(session, conv.id, "assistant", {"text": full_text})

        # Audit every SQL the agent ran this turn (best-effort; never raises)
        await record_queries(
            session,
            user_id=current_user.id,
            conversation_id=conv.id,
            question=request.message,
            entries=orchestrator.audit_entries,
        )

    return generate()


@router.post("/")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    pool=Depends(get_business_pool),  # ensures pool is ready before streaming starts
):
    if current_user.force_password_change:
        raise HTTPException(status_code=403, detail="Password change required before using chat")

    # Backpressure: acquire a concurrency slot, or shed load with 429.
    if not await _acquire_chat_slot():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The assistant is at capacity right now. Please try again in a moment.",
        )
    try:
        generator = await _run_agent(request, current_user, session, pool)
    except Exception:
        _chat_slots.release()  # never leak the slot if setup fails
        raise

    async def _streamed():
        try:
            async for chunk in _sse_stream(generator):
                yield chunk
        finally:
            _chat_slots.release()  # released on completion or client disconnect

    return StreamingResponse(
        _streamed(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/confirm/{query_id}", response_model=DetailResponse)
async def confirm_query(
    query_id: str,
    body: ConfirmRequest,
    _: User = Depends(get_current_user),
):
    delivered = await get_confirmation_broker().signal(query_id, body.approved)
    if not delivered:
        raise HTTPException(status_code=404, detail="Query confirmation expired or not found")
    return DetailResponse(detail="Confirmation received")


@router.get("/conversations", response_model=list[ConversationSummaryOut])
async def list_convs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    convs = await list_conversations(session, current_user.id)
    return [
        ConversationSummaryOut(
            id=c.id,
            title=c.title or "New conversation",
            created_at=c.created_at.isoformat() if c.created_at else None,
            updated_at=c.updated_at.isoformat() if c.updated_at else None,
        )
        for c in convs
    ]


@router.get("/conversations/{conv_id}", response_model=ConversationDetailOut)
async def get_conv(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    conv = await get_conversation(session, conv_id, current_user.id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await get_messages(session, conv_id)
    return ConversationDetailOut(
        id=conv.id,
        title=conv.title or "New conversation",
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=json.loads(m.content),
                created_at=m.created_at.isoformat() if m.created_at else None,
            )
            for m in messages
        ],
    )


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def del_conv(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_conversation(session, conv_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

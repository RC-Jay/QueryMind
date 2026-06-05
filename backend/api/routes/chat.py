import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from db.analytics import get_session, User
from services.conversation_service import (
    get_conversation, list_conversations, delete_conversation, get_messages, rename_conversation,
)
from services.chat_service import run_turn
from services.confirmation import get_confirmation_broker
from api.schemas.chat import (
    ChatRequest, ConfirmRequest, ConversationRenameRequest,
    ConversationSummaryOut, MessageOut, ConversationDetailOut,
)
from api.schemas.common import DetailResponse
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


@router.post("/")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    pool=Depends(get_business_pool),  # ensures pool is ready before streaming starts
):
    if current_user.force_password_change:
        raise HTTPException(status_code=403, detail="Password change required before using chat")

    # Backpressure: acquire a concurrency slot or shed the load with 429.
    if not await _acquire_chat_slot():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The assistant is at capacity right now. Please try again in a moment.",
        )
    try:
        generator = await run_turn(
            session, pool,
            user_id=current_user.id,
            message=request.message,
            conversation_id=request.conversation_id,
        )
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
    return [ConversationSummaryOut.model_validate(c) for c in convs]


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
        title=conv.title,
        messages=[MessageOut.model_validate(m) for m in messages],
    )


@router.patch("/conversations/{conv_id}", response_model=ConversationSummaryOut)
async def rename_conv(
    conv_id: str,
    body: ConversationRenameRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    renamed = await rename_conversation(session, conv_id, current_user.id, body.title)
    if not renamed:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = await get_conversation(session, conv_id, current_user.id)
    return ConversationSummaryOut.model_validate(conv)


@router.delete("/conversations/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def del_conv(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    deleted = await delete_conversation(session, conv_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")

import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from db.analytics import Conversation, Message


async def create_conversation(session: AsyncSession, user_id: int, title: str | None = None) -> Conversation:
    conv = Conversation(id=str(uuid.uuid4()), user_id=user_id, title=title)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def get_conversation(session: AsyncSession, conv_id: str, user_id: int) -> Conversation | None:
    result = await session.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_conversations(session: AsyncSession, user_id: int) -> list[Conversation]:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


async def delete_conversation(session: AsyncSession, conv_id: str, user_id: int) -> bool:
    result = await session.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    await session.execute(delete(Message).where(Message.conversation_id == conv_id))
    await session.delete(conv)
    await session.commit()
    return True


async def append_message(
    session: AsyncSession, conv_id: str, role: str, content: dict
) -> Message:
    msg = Message(id=str(uuid.uuid4()), conversation_id=conv_id, role=role, content=json.dumps(content))
    session.add(msg)
    # update conversation updated_at
    result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if conv:
        conv.updated_at = func.now()
    await session.commit()
    return msg


async def get_messages(session: AsyncSession, conv_id: str) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return result.scalars().all()


async def get_message_count(session: AsyncSession, conv_id: str) -> int:
    """Total number of messages in a conversation."""
    result = await session.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == conv_id)
    )
    return result.scalar() or 0


async def get_recent_messages(session: AsyncSession, conv_id: str, limit: int) -> list[Message]:
    """Last `limit` messages in chronological order. Efficient: fetches only what's needed."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def get_older_messages(session: AsyncSession, conv_id: str, count: int) -> list[Message]:
    """Oldest `count` messages — the pre-window set passed to the summarisation LLM call."""
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
        .limit(count)
    )
    return result.scalars().all()


async def get_conversation_internal(session: AsyncSession, conv_id: str) -> Conversation | None:
    """Load a conversation by id only — no ownership check. Internal/service use only."""
    result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
    return result.scalar_one_or_none()


async def update_conversation_summary(
    session: AsyncSession, conv_id: str, summary: str, checkpoint: str
) -> None:
    """Persist a generated summary and the message_id it was summarised up to."""
    result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if conv:
        conv.summary = summary
        conv.summary_checkpoint = checkpoint
        await session.commit()


async def rename_conversation(
    session: AsyncSession, conv_id: str, user_id: int, title: str
) -> bool:
    """Rename a conversation. Returns False if not found or not owned by user."""
    result = await session.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    conv.title = title[:100]
    await session.commit()
    return True

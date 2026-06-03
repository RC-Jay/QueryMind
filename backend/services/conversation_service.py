import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
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
        from sqlalchemy import func
        conv.updated_at = func.now()
    await session.commit()
    return msg


async def get_messages(session: AsyncSession, conv_id: str) -> list[Message]:
    result = await session.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.created_at)
    )
    return result.scalars().all()


async def set_conversation_title(session: AsyncSession, conv_id: str, title: str) -> None:
    result = await session.execute(select(Conversation).where(Conversation.id == conv_id))
    conv = result.scalar_one_or_none()
    if conv and not conv.title:
        conv.title = title[:100]
        await session.commit()

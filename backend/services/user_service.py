from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.analytics import User
from services.auth_service import hash_password_async
from exceptions import ConflictError, ValidationError, NotFoundError


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


async def create_user(
    session: AsyncSession,
    email: str,
    name: str,
    password: str,
    created_by_id: int,
) -> User:
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")
    user = User(
        email=email,
        name=name,
        password_hash=await hash_password_async(password),
        is_active=True,
        is_superuser=False,
        force_password_change=True,
        created_by=created_by_id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def deactivate_user(session: AsyncSession, user_id: int, requesting_user_id: int) -> User:
    if user_id == requesting_user_id:
        raise ValidationError("Cannot deactivate yourself")
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.is_active = False
    await session.commit()
    await session.refresh(user)
    return user


async def reactivate_user(session: AsyncSession, user_id: int) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user


async def reset_password(session: AsyncSession, user_id: int, new_password: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("User not found")
    user.password_hash = await hash_password_async(new_password)
    user.force_password_change = True
    await session.commit()
    await session.refresh(user)
    return user


async def change_own_password(session: AsyncSession, user_id: int, new_password: str) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    user.password_hash = await hash_password_async(new_password)
    user.force_password_change = False
    await session.commit()
    await session.refresh(user)
    return user

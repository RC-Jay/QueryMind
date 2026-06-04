from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.analytics import BusinessConfig
from db.business_db import init_pool
from services import crypto
from exceptions import ServiceUnavailableError, ValidationError


async def get_config(session: AsyncSession) -> BusinessConfig | None:
    result = await session.execute(select(BusinessConfig).where(BusinessConfig.id == 1))
    return result.scalar_one_or_none()


async def get_config_or_raise(session: AsyncSession) -> BusinessConfig:
    config = await get_config(session)
    if config is None:
        raise ServiceUnavailableError(
            "Business not configured yet. Run the seed script or configure via admin UI."
        )
    return config


async def update_config(session: AsyncSession, data: dict, new_db_url: str | None = None) -> BusinessConfig:
    """Persist business config. Pure persistence — no connection side effects
    (call reload_business_pool separately when the DB URL changes)."""
    config = await get_config(session)
    if config is None:
        if new_db_url is None:
            raise ValidationError("DB URL required for first setup")
        config = BusinessConfig(id=1, db_url_encrypted=crypto.encrypt(new_db_url))
        session.add(config)
    elif new_db_url is not None:
        config.db_url_encrypted = crypto.encrypt(new_db_url)

    for key, value in data.items():
        if hasattr(config, key) and key not in ("id", "db_url_encrypted"):
            setattr(config, key, value)  # JSON columns handle list/dict serialization

    await session.commit()
    await session.refresh(config)
    return config


async def reload_business_pool(session: AsyncSession) -> None:
    """(Re)build the asyncpg pool from the stored config. Call after the DB URL
    changes — kept separate from update_config so persistence has no side effects."""
    config = await get_config_or_raise(session)
    await init_pool(crypto.decrypt(config.db_url_encrypted))


async def ensure_pool_from_config(session: AsyncSession) -> None:
    """Called at app startup to initialise the asyncpg pool if a config exists."""
    config = await get_config(session)
    if config is not None:
        try:
            await init_pool(crypto.decrypt(config.db_url_encrypted))
        except Exception:
            pass  # Pool init failure at startup is non-fatal — admin can fix via UI

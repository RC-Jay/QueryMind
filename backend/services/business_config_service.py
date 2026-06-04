import json
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.analytics import BusinessConfig
from db.business_db import test_connection, init_pool
from config import get_settings
from exceptions import ServiceUnavailableError, ValidationError


def _fernet() -> Fernet:
    return Fernet(get_settings().config_encryption_key.encode())


def encrypt_url(db_url: str) -> str:
    return _fernet().encrypt(db_url.encode()).decode()


def decrypt_url(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()


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
    config = await get_config(session)
    if config is None:
        if new_db_url is None:
            raise ValidationError("DB URL required for first setup")
        config = BusinessConfig(id=1, db_url_encrypted=encrypt_url(new_db_url))
        session.add(config)
    elif new_db_url is not None:
        config.db_url_encrypted = encrypt_url(new_db_url)

    for key, value in data.items():
        if hasattr(config, key) and key != "id" and key != "db_url_encrypted":
            if isinstance(value, (dict, list)):
                setattr(config, key, json.dumps(value))
            else:
                setattr(config, key, value)

    await session.commit()
    await session.refresh(config)
    return config


async def reload_business_pool(session: AsyncSession) -> None:
    """(Re)build the asyncpg pool from the stored config. Call after the DB URL
    changes. Kept separate from update_config so config persistence has no
    connection-management side effects."""
    config = await get_config_or_raise(session)
    await init_pool(decrypt_url(config.db_url_encrypted))


async def ensure_pool_from_config(session: AsyncSession) -> None:
    """Called at app startup to initialise the asyncpg pool if a config exists."""
    config = await get_config(session)
    if config is not None:
        try:
            await init_pool(decrypt_url(config.db_url_encrypted))
        except Exception:
            pass  # Pool init failure at startup is non-fatal — admin can fix via UI


def mask_url(encrypted: str) -> str:
    """Return last 10 chars of decrypted URL for display."""
    try:
        url = decrypt_url(encrypted)
        return "..." + url[-10:]
    except Exception:
        return "***"


def get_parsed_config(config: BusinessConfig) -> dict:
    """Return config with JSON fields parsed and DB URL masked."""
    return {
        "business_name": config.business_name,
        "business_description": config.business_description,
        "db_url_masked": mask_url(config.db_url_encrypted),
        "domain_context": config.domain_context,
        "business_rules": json.loads(config.business_rules),
        "table_descriptions": json.loads(config.table_descriptions),
        "kpi_definitions": json.loads(config.kpi_definitions),
        "starter_questions": json.loads(config.starter_questions),
        "explain_cost_threshold": config.explain_cost_threshold,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }

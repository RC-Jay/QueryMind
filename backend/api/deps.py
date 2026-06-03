"""
Shared FastAPI dependencies.
"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db.analytics import get_session
import db.business_db as business_db
from services.business_config_service import get_config, decrypt_url
import logging

logger = logging.getLogger(__name__)


async def get_business_pool(session: AsyncSession = Depends(get_session)):
    """
    Returns the asyncpg pool, lazily initialising it from business_config if
    it wasn't ready at startup (e.g. PostgreSQL was unreachable then).
    """
    if business_db._pool is None:
        config = await get_config(session)
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Business database not configured. Set up the connection via Admin → Business Setup.",
            )
        try:
            url = decrypt_url(config.db_url_encrypted)
            await business_db.init_pool(url)
            logger.info("Business DB pool initialised on first request.")
        except Exception as exc:
            logger.error("Failed to initialise business DB pool: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot connect to business database: {exc}",
            )
    return business_db._pool

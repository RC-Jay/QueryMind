"""
Shared FastAPI dependencies — the single import surface for all route-level
`Depends(...)` wiring.

This is the only place that bridges pure logic (services/, db/) to the HTTP
layer: it resolves the current user from a bearer token and hands out
request-scoped resources (DB session, business connection pool). Domain
errors raised here flow through the central handler in main.py.
"""
import logging
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.analytics import get_session, AsyncSessionLocal, User
import db.business_db as business_db
from services.auth_service import decode_token
from services.business_config_service import get_config, decrypt_url
from exceptions import AuthError, ForbiddenError, ServiceUnavailableError

logger = logging.getLogger(__name__)

# Re-export so routes have one import surface for all dependencies.
__all__ = ["get_session", "get_current_user", "require_superuser", "get_business_pool"]

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    """Resolve the authenticated user from the bearer access token.

    decode_token raises InvalidTokenError (an AppError) on a bad token, which
    the central exception handler turns into a 401 — no try/except needed here.
    """
    payload = decode_token(credentials.credentials, expected_type="access")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == int(payload["sub"])))
        user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("User not found or inactive")
    return user


async def require_superuser(user: User = Depends(get_current_user)) -> User:
    """Guard for superuser-only routes."""
    if not user.is_superuser:
        raise ForbiddenError("Superuser access required")
    return user


async def get_business_pool(session: AsyncSession = Depends(get_session)):
    """
    Returns the asyncpg pool, lazily initialising it from business_config if
    it wasn't ready at startup (e.g. PostgreSQL was unreachable then).
    """
    if business_db._pool is None:
        config = await get_config(session)
        if config is None:
            raise ServiceUnavailableError(
                "Business database not configured. Set up the connection via Admin → Business Setup."
            )
        try:
            url = decrypt_url(config.db_url_encrypted)
            await business_db.init_pool(url)
            logger.info("Business DB pool initialised on first request.")
        except Exception as exc:
            logger.error("Failed to initialise business DB pool: %s", exc)
            raise ServiceUnavailableError(f"Cannot connect to business database: {exc}")
    return business_db._pool

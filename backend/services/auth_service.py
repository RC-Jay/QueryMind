"""
Pure authentication logic — password hashing and JWT token handling.

This module is transport-agnostic: it has no knowledge of FastAPI or HTTP.
FastAPI dependency wiring (get_current_user, require_superuser) lives in
api/deps.py and builds on these primitives.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
from config import get_settings
from exceptions import InvalidTokenError


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# bcrypt is deliberately slow (~50-100ms) and releases the GIL, so offloading it
# to a thread gives real parallelism and keeps the event loop responsive. Use
# these in the async request path; the sync versions remain for CLI scripts/tests.
async def hash_password_async(plain: str) -> str:
    return await asyncio.to_thread(hash_password, plain)


async def verify_password_async(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, plain, hashed)


def _create_token(data: dict, expires_delta: timedelta) -> str:
    settings = get_settings()
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_access_token(user_id: int, is_superuser: bool) -> str:
    settings = get_settings()
    return _create_token(
        {"sub": str(user_id), "su": is_superuser, "type": "access"},
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(user_id: int) -> str:
    settings = get_settings()
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )


def decode_token(token: str, expected_type: str = "access") -> dict:
    """Decode and validate a JWT. Raises InvalidTokenError on any problem."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            raise JWTError("Wrong token type")
        return payload
    except JWTError:
        raise InvalidTokenError("Invalid or expired token")

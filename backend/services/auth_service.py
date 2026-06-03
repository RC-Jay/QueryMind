from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import get_settings

_bearer = HTTPBearer()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


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
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            raise JWTError("Wrong token type")
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
):
    payload = decode_token(credentials.credentials, expected_type="access")
    from db.analytics import AsyncSessionLocal, User
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == int(payload["sub"])))
        user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def require_superuser(user=Depends(get_current_user)):
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    return user

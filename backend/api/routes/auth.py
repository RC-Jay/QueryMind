from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.analytics import get_session, User
from services.auth_service import (
    verify_password, create_access_token, create_refresh_token,
    decode_token, InvalidTokenError,
)
from services.user_service import change_own_password
from api.deps import get_current_user
from api.schemas.auth import (
    LoginRequest, ChangePasswordRequest, UserOut, LoginResponse, TokenResponse,
)
from api.schemas.common import DetailResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        name=user.name,
        email=user.email,
        is_superuser=user.is_superuser,
        force_password_change=user.force_password_change,
    )


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, response: Response, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    access_token = create_access_token(user.id, user.is_superuser)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
        path="/api/auth",
    )
    return LoginResponse(access_token=access_token, user=_user_out(user))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(response: Response, refresh_token: str | None = Cookie(default=None), session: AsyncSession = Depends(get_session)):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await session.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(user.id, user.is_superuser)
    new_refresh = create_refresh_token(user.id)
    response.set_cookie(key="refresh_token", value=new_refresh, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7, path="/api/auth")
    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=DetailResponse)
async def logout(response: Response):
    response.delete_cookie(key="refresh_token", path="/api/auth")
    return DetailResponse(detail="Logged out")


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)


@router.post("/change-password", response_model=DetailResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    await change_own_password(session, current_user.id, body.new_password)
    return DetailResponse(detail="Password changed successfully")

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from db.analytics import get_session, User
from services.auth_service import require_superuser
from services.user_service import (
    list_users, create_user, deactivate_user, reactivate_user, reset_password,
)
from services.business_config_service import (
    get_config_or_raise, update_config, get_parsed_config,
)
from db.business_db import test_connection

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── User management ───────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.get("/users")
async def get_users(
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    users = await list_users(session)
    return [
        {
            "id": u.id,
            "email": u.email,
            "name": u.name,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "force_password_change": u.force_password_change,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def add_user(
    body: CreateUserRequest,
    superuser: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    user = await create_user(session, body.email, body.name, body.password, superuser.id)
    return {"id": user.id, "email": user.email, "name": user.name}


@router.post("/users/{user_id}/deactivate")
async def deactivate(
    user_id: int,
    superuser: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    await deactivate_user(session, user_id, superuser.id)
    return {"detail": "User deactivated"}


@router.post("/users/{user_id}/reactivate")
async def reactivate(
    user_id: int,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    await reactivate_user(session, user_id)
    return {"detail": "User reactivated"}


@router.post("/users/{user_id}/reset-password")
async def reset_pwd(
    user_id: int,
    body: ResetPasswordRequest,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    await reset_password(session, user_id, body.new_password)
    return {"detail": "Password reset — user must change on next login"}


# ── Business config ───────────────────────────────────────────────────────────

class BusinessConfigRequest(BaseModel):
    business_name: str
    business_description: str
    db_url: str | None = None  # None means "keep existing"
    domain_context: str
    business_rules: list[dict]
    table_descriptions: dict
    kpi_definitions: list[dict]
    starter_questions: list[str]
    explain_cost_threshold: int = 50000


class TestConnectionRequest(BaseModel):
    db_url: str


@router.get("/business-config")
async def get_business_config(
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    config = await get_config_or_raise(session)
    return get_parsed_config(config)


@router.put("/business-config")
async def put_business_config(
    body: BusinessConfigRequest,
    _: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
):
    data = body.model_dump(exclude={"db_url"})
    config = await update_config(session, data, new_db_url=body.db_url)
    return get_parsed_config(config)


@router.post("/business-config/test-connection")
async def test_db_connection(
    body: TestConnectionRequest,
    _: User = Depends(require_superuser),
):
    ok, message = await test_connection(body.db_url)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Connection failed: {message}")
    return {"detail": message}

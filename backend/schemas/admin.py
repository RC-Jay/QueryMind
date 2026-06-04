from pydantic import BaseModel
from typing import Any


# ── Requests ──────────────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: str
    name: str
    password: str


class ResetPasswordRequest(BaseModel):
    new_password: str


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


# ── Responses ─────────────────────────────────────────────────────────────────

class AdminUserOut(BaseModel):
    """Full user row shown to a superuser in the user management table."""
    id: int
    email: str
    name: str
    is_active: bool
    is_superuser: bool
    force_password_change: bool
    created_at: str | None = None


class CreateUserResponse(BaseModel):
    id: int
    email: str
    name: str


class BusinessConfigOut(BaseModel):
    """Business config with the DB URL masked (never exposes credentials)."""
    business_name: str
    business_description: str
    db_url_masked: str
    domain_context: str
    business_rules: list[dict]
    table_descriptions: dict
    kpi_definitions: list[dict]
    starter_questions: list[str]
    explain_cost_threshold: int
    updated_at: str | None = None

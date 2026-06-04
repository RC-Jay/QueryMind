from pydantic import BaseModel, ConfigDict


# ── Requests ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    new_password: str


# ── Responses ─────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    """Identity profile returned to the authenticated user (login + /me).
    Build with UserOut.model_validate(user)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    is_superuser: bool
    force_password_change: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

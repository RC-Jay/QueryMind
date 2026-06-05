import json
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from services import crypto


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


class LLMConfigRequest(BaseModel):
    provider: str                  # "azure" | "claude"
    model: str                     # Azure deployment name or Claude model id
    api_key: str | None = None     # None = keep existing key
    endpoint: str | None = None    # Azure only
    api_version: str | None = None # Azure only


# ── Responses ─────────────────────────────────────────────────────────────────

class AdminUserOut(BaseModel):
    """Full user row shown to a superuser. Build with .model_validate(user)."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    name: str
    is_active: bool
    is_superuser: bool
    force_password_change: bool
    created_at: datetime | None = None  # serialized to ISO 8601


class CreateUserResponse(BaseModel):
    id: int
    email: str
    name: str


def _maybe_json(value):
    """Accept a JSON string (Text column) or an already-parsed value (JSON column)."""
    return json.loads(value) if isinstance(value, str) else value


class BusinessConfigOut(BaseModel):
    """Business config returned to superusers. Full DB URL is decrypted — this
    endpoint is superuser-only so credentials are safe to return."""
    business_name: str
    business_description: str
    db_url: str               # full decrypted URL — superuser-only endpoint
    domain_context: str
    business_rules: list[dict]
    table_descriptions: dict
    kpi_definitions: list[dict]
    starter_questions: list[str]
    explain_cost_threshold: int
    updated_at: datetime | None = None

    @classmethod
    def from_model(cls, c) -> "BusinessConfigOut":
        return cls(
            business_name=c.business_name,
            business_description=c.business_description,
            db_url=crypto.decrypt(c.db_url_encrypted),
            domain_context=c.domain_context,
            business_rules=_maybe_json(c.business_rules),
            table_descriptions=_maybe_json(c.table_descriptions),
            kpi_definitions=_maybe_json(c.kpi_definitions),
            starter_questions=_maybe_json(c.starter_questions),
            explain_cost_threshold=c.explain_cost_threshold,
            updated_at=c.updated_at,
        )


class LLMConfigOut(BaseModel):
    """LLM config with the API key masked (never exposes the full key)."""
    provider: str
    model: str
    endpoint: str | None = None
    api_version: str | None = None
    api_key_masked: str
    updated_at: datetime | None = None

    @classmethod
    def from_model(cls, c) -> "LLMConfigOut":
        return cls(
            provider=c.provider,
            model=c.model,
            endpoint=c.endpoint,
            api_version=c.api_version,
            api_key_masked=crypto.mask(c.api_key_encrypted),
            updated_at=c.updated_at,
        )

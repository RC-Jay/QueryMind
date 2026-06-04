"""
LLM configuration: which provider/model the deployment uses, stored in the
analytics DB (api key encrypted). Superuser-editable via the admin UI.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.analytics import LLMConfig
from services import crypto
from config import get_settings
from exceptions import ServiceUnavailableError, ValidationError

SUPPORTED_PROVIDERS = {"azure", "claude"}


async def get_llm_config(session: AsyncSession) -> LLMConfig | None:
    result = await session.execute(select(LLMConfig).where(LLMConfig.id == 1))
    return result.scalar_one_or_none()


async def get_llm_config_or_raise(session: AsyncSession) -> LLMConfig:
    config = await get_llm_config(session)
    if config is None:
        raise ServiceUnavailableError(
            "No LLM configured. Set one up in Admin → AI Model."
        )
    return config


async def update_llm_config(
    session: AsyncSession,
    provider: str,
    model: str,
    api_key: str | None = None,
    endpoint: str | None = None,
    api_version: str | None = None,
) -> LLMConfig:
    provider = (provider or "").lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValidationError(f"Unsupported provider: {provider!r}. Choose one of {sorted(SUPPORTED_PROVIDERS)}.")
    if provider == "azure" and not endpoint:
        raise ValidationError("Azure OpenAI requires an endpoint.")
    if not model:
        raise ValidationError("A model (Azure deployment name or Claude model id) is required.")

    config = await get_llm_config(session)
    if config is None:
        if not api_key:
            raise ValidationError("An API key is required for first setup.")
        config = LLMConfig(id=1, provider=provider, model=model,
                           api_key_encrypted=crypto.encrypt(api_key),
                           endpoint=endpoint, api_version=api_version)
        session.add(config)
    else:
        config.provider = provider
        config.model = model
        config.endpoint = endpoint
        config.api_version = api_version
        if api_key:  # only overwrite when a new key is supplied
            config.api_key_encrypted = crypto.encrypt(api_key)

    await session.commit()
    await session.refresh(config)
    return config


def get_parsed_llm_config(config: LLMConfig) -> dict:
    """Public-safe view: API key masked, never returned in full."""
    return {
        "provider": config.provider,
        "model": config.model,
        "endpoint": config.endpoint,
        "api_version": config.api_version,
        "api_key_masked": crypto.mask(config.api_key_encrypted),
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


async def ensure_llm_config_from_env(session: AsyncSession) -> None:
    """
    Migration/bootstrap: if no LLM config exists yet but Azure env vars are
    present, seed the config from them. Keeps existing deployments working;
    after this the DB is the source of truth.
    """
    if await get_llm_config(session) is not None:
        return
    settings = get_settings()
    api_key = getattr(settings, "azure_openai_api_key", None)
    endpoint = getattr(settings, "azure_openai_endpoint", None)
    deployment = getattr(settings, "azure_openai_deployment", None)
    if api_key and endpoint and deployment:
        await update_llm_config(
            session,
            provider="azure",
            model=deployment,
            api_key=api_key,
            endpoint=endpoint,
            api_version=getattr(settings, "azure_openai_api_version", None),
        )

import pytest
from services import llm_config_service as svc
from services import crypto
from exceptions import ServiceUnavailableError, ValidationError


async def test_raises_when_unconfigured(analytics_session):
    with pytest.raises(ServiceUnavailableError):
        await svc.get_llm_config_or_raise(analytics_session)


async def test_create_azure_config(analytics_session):
    cfg = await svc.update_llm_config(
        analytics_session, provider="azure", model="gpt-4o-mini",
        api_key="sk-secret", endpoint="https://x.openai.azure.com/", api_version="2025-01-01-preview",
    )
    assert cfg.provider == "azure"
    assert crypto.decrypt(cfg.api_key_encrypted) == "sk-secret"
    from api.schemas.admin import LLMConfigOut
    out = LLMConfigOut.from_model(cfg)
    assert "sk-secret" not in out.api_key_masked   # never leaks the key
    assert out.model == "gpt-4o-mini"


async def test_create_claude_config(analytics_session):
    cfg = await svc.update_llm_config(
        analytics_session, provider="claude", model="claude-sonnet-4-5", api_key="ak-123",
    )
    assert cfg.provider == "claude"
    assert cfg.endpoint is None


async def test_azure_requires_endpoint(analytics_session):
    with pytest.raises(ValidationError):
        await svc.update_llm_config(
            analytics_session, provider="azure", model="gpt-4o", api_key="k", endpoint=None,
        )


async def test_unsupported_provider_rejected(analytics_session):
    with pytest.raises(ValidationError):
        await svc.update_llm_config(analytics_session, provider="gemini", model="g", api_key="k")


async def test_first_setup_requires_api_key(analytics_session):
    with pytest.raises(ValidationError):
        await svc.update_llm_config(
            analytics_session, provider="claude", model="claude-sonnet-4-5", api_key=None,
        )


async def test_update_keeps_key_when_blank(analytics_session):
    await svc.update_llm_config(
        analytics_session, provider="claude", model="claude-sonnet-4-5", api_key="original-key",
    )
    # Update model only, no new key supplied → key preserved
    cfg = await svc.update_llm_config(
        analytics_session, provider="claude", model="claude-opus-4-1", api_key=None,
    )
    assert cfg.model == "claude-opus-4-1"
    assert crypto.decrypt(cfg.api_key_encrypted) == "original-key"


async def test_switch_provider_azure_to_claude(analytics_session):
    await svc.update_llm_config(
        analytics_session, provider="azure", model="gpt-4o", api_key="azkey",
        endpoint="https://x/", api_version="v",
    )
    cfg = await svc.update_llm_config(
        analytics_session, provider="claude", model="claude-sonnet-4-5", api_key="ankey",
    )
    assert cfg.provider == "claude"
    assert crypto.decrypt(cfg.api_key_encrypted) == "ankey"

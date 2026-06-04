import pytest
from types import SimpleNamespace
from agent.llm.factory import create_llm_provider
from agent.llm.azure_provider import AzureOpenAIProvider
from agent.llm.claude_provider import ClaudeProvider
from agent.llm.base import LLMProvider
from services import crypto


def _config(provider, model, endpoint=None, api_version=None, api_key="secret-key"):
    return SimpleNamespace(
        provider=provider,
        model=model,
        endpoint=endpoint,
        api_version=api_version,
        api_key_encrypted=crypto.encrypt(api_key),
    )


def test_builds_azure_provider():
    p = create_llm_provider(_config("azure", "gpt-4o-mini", endpoint="https://x/", api_version="v"))
    assert isinstance(p, AzureOpenAIProvider)
    assert isinstance(p, LLMProvider)


def test_builds_claude_provider():
    p = create_llm_provider(_config("claude", "claude-sonnet-4-5"))
    assert isinstance(p, ClaudeProvider)
    assert isinstance(p, LLMProvider)


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        create_llm_provider(_config("gemini", "gemini-pro"))

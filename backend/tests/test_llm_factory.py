import pytest
from types import SimpleNamespace
from agent.llm.factory import create_llm_provider
from agent.llm.azure_provider import AzureOpenAIProvider
from agent.llm.base import LLMProvider


def _settings(provider):
    return SimpleNamespace(
        llm_provider=provider,
        azure_openai_endpoint="https://x.example.com/",
        azure_openai_api_key="k",
        azure_openai_api_version="2025-01-01-preview",
        azure_openai_deployment="d",
    )


def test_builds_azure_provider():
    provider = create_llm_provider(_settings("azure"))
    assert isinstance(provider, AzureOpenAIProvider)
    assert isinstance(provider, LLMProvider)  # satisfies the Strategy protocol


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        create_llm_provider(_settings("gemini"))  # not implemented yet


def test_default_is_azure():
    s = SimpleNamespace(
        azure_openai_endpoint="https://x/", azure_openai_api_key="k",
        azure_openai_api_version="v", azure_openai_deployment="d",
    )  # no llm_provider attribute → defaults to azure
    assert isinstance(create_llm_provider(s), AzureOpenAIProvider)

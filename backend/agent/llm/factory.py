"""
Factory that builds the configured LLMProvider from the stored LLMConfig.

Provider + credentials come from the analytics DB (Admin → AI Model), not the
environment. To add another backend (e.g. Gemini):
  1. Create agent/llm/<name>_provider.py implementing LLMProvider
  2. Add a branch below keyed on config.provider
Nothing else in the app changes.
"""
from agent.llm.base import LLMProvider
from agent.llm.azure_provider import AzureOpenAIProvider
from agent.llm.claude_provider import ClaudeProvider
from services import crypto


def create_llm_provider(config) -> LLMProvider:
    """`config` is an LLMConfig row (provider, model, endpoint, api_version,
    api_key_encrypted)."""
    provider = (config.provider or "").lower()
    api_key = crypto.decrypt(config.api_key_encrypted)

    if provider == "azure":
        return AzureOpenAIProvider(
            endpoint=config.endpoint,
            api_key=api_key,
            api_version=config.api_version,
            deployment=config.model,
        )

    if provider == "claude":
        return ClaudeProvider(api_key=api_key, model=config.model)

    raise ValueError(f"Unsupported LLM provider: {provider!r}")

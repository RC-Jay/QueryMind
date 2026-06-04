"""
Factory that builds the configured LLMProvider.

To add a new backend (e.g. Gemini):
  1. Create agent/llm/gemini_provider.py implementing LLMProvider
  2. Add an `elif provider == "gemini"` branch below
  3. Set LLM_PROVIDER=gemini in the environment
Nothing else in the app changes.
"""
from agent.llm.base import LLMProvider
from agent.llm.azure_provider import AzureOpenAIProvider


def create_llm_provider(settings) -> LLMProvider:
    provider = (getattr(settings, "llm_provider", "azure") or "azure").lower()

    if provider == "azure":
        return AzureOpenAIProvider(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            deployment=settings.azure_openai_deployment,
        )

    # elif provider == "gemini":
    #     return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    raise ValueError(f"Unsupported LLM provider: {provider!r}")

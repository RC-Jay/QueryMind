"""
LLM provider factory — registry pattern + short TTL cache.

## Registry
Providers register themselves via a dict keyed on the provider name stored in
the llm_config table. To add a new backend (e.g. Gemini):
  1. Create agent/llm/gemini_provider.py implementing LLMProvider + from_config()
  2. Add one line to _REGISTRY below
Nothing else in the app changes.

## TTL cache
Each provider instantiation creates a new httpx.AsyncClient (inside the vendor
SDK), which means a new connection pool per turn if we build naively. The TTL
cache avoids that: the same provider instance is reused for `_CACHE_TTL_SECONDS`
and its connection pool is long-lived. When an admin changes the LLM config in
the UI, the next request after the TTL sees the new config automatically.
"""
import time
import logging
from typing import NamedTuple

from agent.llm.base import LLMProvider
from agent.llm.azure_provider import AzureOpenAIProvider
from agent.llm.claude_provider import ClaudeProvider
from services import crypto

log = logging.getLogger(__name__)

# ── Registry ──────────────────────────────────────────────────────────────────
# Maps the provider name (as stored in llm_config.provider) to its class.
# Each class must implement LLMProvider and expose a from_config(api_key, config)
# classmethod that knows how to extract its own constructor args from the row.

_REGISTRY: dict[str, type] = {
    "azure": AzureOpenAIProvider,
    "claude": ClaudeProvider,
}

# ── TTL cache ─────────────────────────────────────────────────────────────────
# A single cached entry: (provider_instance, expiry_timestamp).
# Keyed on a tuple of all config fields that affect the provider so a config
# change is detected immediately after the TTL (not just on restart).

_CACHE_TTL_SECONDS = 60  # stale config visible for at most 60 s after admin change


class _CacheEntry(NamedTuple):
    provider: LLMProvider
    expires_at: float


_cache: _CacheEntry | None = None


def _cache_key(config) -> tuple:
    """Stable identity for a config row — if any field changes, cache misses."""
    return (
        (config.provider or "").lower(),
        config.model,
        config.endpoint,
        config.api_version,
        config.api_key_encrypted,  # encrypted; changes on key rotation
    )


_last_key: tuple | None = None


def create_llm_provider(config) -> LLMProvider:
    """Return a cached LLMProvider, rebuilding only when config changes or TTL expires.

    `config` is an LLMConfig ORM row (provider, model, endpoint, api_version,
    api_key_encrypted). The caller does not need to decrypt the API key.
    """
    global _cache, _last_key

    now = time.monotonic()
    key = _cache_key(config)

    if _cache is not None and _last_key == key and _cache.expires_at > now:
        return _cache.provider

    # Cache miss — build a fresh provider.
    provider_name = (config.provider or "").lower()
    cls = _REGISTRY.get(provider_name)
    if cls is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown LLM provider {config.provider!r}. Supported: {supported}"
        )

    api_key = crypto.decrypt(config.api_key_encrypted)
    provider = cls.from_config(api_key, config)
    log.info("llm_factory: built %s provider (model=%s)", provider_name, config.model)

    _cache = _CacheEntry(provider=provider, expires_at=now + _CACHE_TTL_SECONDS)
    _last_key = key
    return provider

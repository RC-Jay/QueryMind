from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="/Users/ravada/Projects/DataAnalysis/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM provider selection (azure | gemini | ...)
    llm_provider: str = "azure"

    # Azure OpenAI
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str
    azure_openai_api_version: str

    # Analytics SQLite
    analytics_db_path: str

    # Encryption key for business DB URL at rest (Fernet)
    config_encryption_key: str

    # Auth
    jwt_secret_key: str
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Redis — used for the expensive-query confirmation signal (and future caching).
    # Empty → falls back to an in-process broker (single-worker / local dev / tests).
    redis_url: str = ""

    # App
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()

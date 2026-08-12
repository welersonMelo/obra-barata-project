"""Application settings."""

from functools import lru_cache
from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ROOT_PATH_BACKEND: str = ""
    LOG_LEVEL: str = "INFO"

    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4.1"
    LLM_TEMPERATURE: float = 0.2
    LLM_REASONING_EFFORT: str = "low"
    LLM_REQUEST_TIMEOUT_SECONDS: int = 300
    LLM_MAX_RETRIES: int = 3

    IFC_STORAGE_DIR: Path = Path("/data/ifc")

    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_API_VERSION: str | None = None
    AZURE_OPENAI_AZURE_ENDPOINT: str | None = None
    AZURE_OPENAI_DEPLOYMENT: str | None = None
    LLM_MAX_CONTENT_CHARS: int = 120_000

    @property
    def openai_api_key(self) -> str | None:
        """Return the OpenAI API key accepting the notebook's lowercase name too."""

        return self.OPENAI_API_KEY or os.getenv("openai_api_key")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()

"""OpenAI chat model construction for IFC analysis."""

import os

from langchain_openai import ChatOpenAI

from app.settings import get_settings


class OpenAIConfigurationError(RuntimeError):
    """Raised when OpenAI settings are missing."""


def build_openai_chat_model() -> ChatOpenAI:
    """Build the OpenAI chat model used by IFC services."""

    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise OpenAIConfigurationError("Missing OPENAI_API_KEY or openai_api_key.")
    os.environ["OPENAI_API_KEY"] = api_key
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.LLM_MAX_RETRIES,
    )

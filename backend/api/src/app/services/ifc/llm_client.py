"""OpenAI chat model construction for IFC analysis."""

import os

from langchain_openai import ChatOpenAI

from app.settings import get_settings


class OpenAIConfigurationError(RuntimeError):
    """Raised when OpenAI settings are missing."""


def _supports_reasoning_effort(model: str) -> bool:
    normalized_model = model.lower()
    return normalized_model.startswith(("gpt-5", "o1", "o3", "o4"))


def build_openai_chat_model() -> ChatOpenAI:
    """Build the OpenAI chat model used by IFC services."""

    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise OpenAIConfigurationError("Missing OPENAI_API_KEY or openai_api_key.")
    os.environ["OPENAI_API_KEY"] = api_key
    model_kwargs = {
        "model": settings.OPENAI_MODEL,
        "temperature": settings.LLM_TEMPERATURE,
        "timeout": settings.LLM_REQUEST_TIMEOUT_SECONDS,
        "max_retries": settings.LLM_MAX_RETRIES,
    }
    if _supports_reasoning_effort(settings.OPENAI_MODEL):
        model_kwargs["reasoning_effort"] = settings.LLM_REASONING_EFFORT

    return ChatOpenAI(**model_kwargs)

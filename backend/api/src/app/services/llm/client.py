"""Azure OpenAI chat model construction for the LLM service."""

from langchain_openai import AzureChatOpenAI

from app.settings import get_settings


class LLMConfigurationError(RuntimeError):
    """Raised when the Azure OpenAI credentials are not configured."""


def build_chat_model() -> AzureChatOpenAI:
    """Build an Azure OpenAI chat model from application settings.

    Raises:
        LLMConfigurationError: When required Azure OpenAI settings are missing.
    """
    settings = get_settings()
    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_API_KEY", settings.AZURE_OPENAI_API_KEY),
            ("AZURE_OPENAI_API_VERSION", settings.AZURE_OPENAI_API_VERSION),
            ("AZURE_OPENAI_AZURE_ENDPOINT", settings.AZURE_OPENAI_AZURE_ENDPOINT),
        )
        if not value
    ]
    if missing:
        raise LLMConfigurationError(
            f"Missing Azure OpenAI settings: {', '.join(missing)}"
        )
    return AzureChatOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_AZURE_ENDPOINT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_deployment=settings.AZURE_OPENAI_DEPLOYMENT,
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        temperature=settings.LLM_TEMPERATURE,
        timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        max_retries=settings.LLM_MAX_RETRIES,
    )

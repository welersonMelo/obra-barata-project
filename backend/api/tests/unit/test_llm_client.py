from types import SimpleNamespace

from app.services.ifc import llm_client


class FakeChatOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def _settings(model="gpt-4.1", temperature=0.2):
    return SimpleNamespace(
        openai_api_key="test-key",
        OPENAI_MODEL=model,
        LLM_TEMPERATURE=temperature,
        LLM_REASONING_EFFORT="low",
        LLM_REQUEST_TIMEOUT_SECONDS=300,
        LLM_MAX_RETRIES=3,
    )


def test_build_openai_chat_model_uses_gpt_41_without_reasoning_effort(monkeypatch):
    monkeypatch.setattr(llm_client, "get_settings", lambda: _settings())
    monkeypatch.setattr(llm_client, "ChatOpenAI", FakeChatOpenAI)

    chat_model = llm_client.build_openai_chat_model()

    assert chat_model.kwargs == {
        "model": "gpt-4.1",
        "temperature": 0.2,
        "timeout": 300,
        "max_retries": 3,
    }


def test_build_openai_chat_model_keeps_reasoning_effort_for_reasoning_models(
    monkeypatch,
):
    monkeypatch.setattr(llm_client, "get_settings", lambda: _settings(model="gpt-5"))
    monkeypatch.setattr(llm_client, "ChatOpenAI", FakeChatOpenAI)

    chat_model = llm_client.build_openai_chat_model()

    assert chat_model.kwargs["reasoning_effort"] == "low"


def test_settings_reads_lowercase_serper_api_key(monkeypatch):
    from app.settings import Settings

    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    monkeypatch.setenv("serper_api_key", "serper-test-key")

    assert Settings().serper_api_key == "serper-test-key"

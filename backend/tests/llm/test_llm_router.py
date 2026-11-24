import pytest
from pydantic import BaseModel, ValidationError
from types import SimpleNamespace

from app.llm import llm_router


class Reply(BaseModel):
    """Expected structure for structured LLM responses."""

    message: str


# --------------------------------------------------
# Model configuration tests
# --------------------------------------------------

def test_load_model_configs_prioritizes_primary_provider(
    monkeypatch, tmp_path
):
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        """
models:
  - provider: openrouter
    model: model-a
    api_key_env: OPENROUTER_API_KEY
  - provider: groq
    model: model-b
    api_key_env: GROQ_API_KEY
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    configs = llm_router.load_model_configs()

    assert [config["provider"] for config in configs] == [
        "groq",
        "openrouter",
    ]


@pytest.mark.parametrize(
    "yaml_content, error_message",
    [
        ("models: []", "non-empty models list"),
        ("models: null", "non-empty models list"),
        (
            """
models:
  - provider: gemini
    model: test-model
    api_key_env: API_KEY
""",
            "Unsupported LLM provider",
        ),
        (
            """
models:
  - provider: groq
    model: test-model
""",
            "api_key_env",
        ),
        (
            """
models:
  - provider: groq
    api_key_env: API_KEY
""",
            "model",
        ),
        (
            """
models:
  - provider: groq
    model: test-model
""",
            "api_key_env",
        ),
    ],
)
def test_load_model_configs_rejects_invalid_configuration(
    monkeypatch, tmp_path, yaml_content, error_message
):
    config_file = tmp_path / "models.yaml"
    config_file.write_text(yaml_content, encoding="utf-8")

    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    with pytest.raises(ValueError, match=error_message):
        llm_router.load_model_configs()


def test_load_model_configs_rejects_non_dictionary_entry(
    monkeypatch, tmp_path
):
    config_file = tmp_path / "models.yaml"
    config_file.write_text(
        """
models:
  - invalid-entry
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    with pytest.raises(ValueError, match="Invalid model configuration"):
        llm_router.load_model_configs()


def test_load_model_configs_file_not_found(monkeypatch, tmp_path):
    missing_file = tmp_path / "missing.yaml"

    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(missing_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    with pytest.raises(FileNotFoundError, match="configuration not found"):
        llm_router.load_model_configs()


# --------------------------------------------------
# Model name resolution tests
# --------------------------------------------------

def test_resolve_model_name_from_settings(monkeypatch):
    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(GROQ_MODEL="llama-test"),
    )

    model_name = llm_router.resolve_model_name(
        {
            "provider": "groq",
            "model": "${GROQ_MODEL}",
            "api_key_env": "GROQ_API_KEY",
        }
    )

    assert model_name == "llama-test"


def test_resolve_model_name_without_placeholder():
    model_name = llm_router.resolve_model_name(
        {
            "provider": "groq",
            "model": "llama-test",
            "api_key_env": "GROQ_API_KEY",
        }
    )

    assert model_name == "llama-test"


def test_resolve_model_name_raises_when_setting_is_missing(monkeypatch):
    monkeypatch.setattr(llm_router, "settings", SimpleNamespace())

    with pytest.raises(ValueError, match="not configured"):
        llm_router.resolve_model_name(
            {
                "provider": "groq",
                "model": "${MISSING_MODEL}",
                "api_key_env": "GROQ_API_KEY",
            }
        )


# --------------------------------------------------
# LLM initialization tests
# --------------------------------------------------

def test_create_groq_llm(monkeypatch):
    captured = {}

    def fake_chat_groq(**kwargs):
        captured.update(kwargs)
        return "fake-groq"

    monkeypatch.setattr(llm_router, "ChatGroq", fake_chat_groq)
    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(GROQ_API_KEY="test-key"),
    )

    result = llm_router.create_llm(
        {
            "provider": "groq",
            "model": "llama-test",
            "api_key_env": "GROQ_API_KEY",
        },
        temperature=0.2,
    )

    assert result == "fake-groq"
    assert captured == {
        "model": "llama-test",
        "api_key": "test-key",
        "temperature": 0.2,
    }


def test_create_openrouter_llm(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return "fake-openrouter"

    monkeypatch.setattr(llm_router, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(
            OPENROUTER_API_KEY="test-key",
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        ),
    )

    result = llm_router.create_llm(
        {
            "provider": "openrouter",
            "model": "provider/model",
            "api_key_env": "OPENROUTER_API_KEY",
        }
    )

    assert result == "fake-openrouter"
    assert captured == {
        "model": "provider/model",
        "api_key": "test-key",
        "base_url": "https://openrouter.ai/api/v1",
        "temperature": 0.0,
    }


def test_create_llm_raises_when_api_key_is_missing(monkeypatch):
    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(GROQ_API_KEY=None),
    )

    with pytest.raises(ValueError, match="GROQ_API_KEY is not configured"):
        llm_router.create_llm(
            {
                "provider": "groq",
                "model": "llama-test",
                "api_key_env": "GROQ_API_KEY",
            }
        )


def test_create_llm_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setattr(
        llm_router,
        "settings",
        SimpleNamespace(TEST_API_KEY="test-key"),
    )

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        llm_router.create_llm(
            {
                "provider": "gemini",
                "model": "test-model",
                "api_key_env": "TEST_API_KEY",
            }
        )


# --------------------------------------------------
# Rate-limit and token-error detection tests
# --------------------------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "429 Too Many Requests",
        "rate limit reached",
        "ratelimit exceeded",
        "quota exceeded",
        "token limit reached",
        "tokens per minute exceeded",
        "TPM limit reached",
        "RPM limit reached",
        "maximum context length exceeded",
        "context window exceeded",
        "insufficient_quota",
        "resource has been exhausted",
        "overloaded",
    ],
)
def test_detects_rate_or_token_errors(message):
    assert llm_router.is_rate_limit_or_token_error(Exception(message))


@pytest.mark.parametrize(
    "message",
    [
        "invalid request",
        "authentication failed",
        "model not found",
        "permission denied",
    ],
)
def test_regular_errors_are_not_rate_or_token_errors(message):
    assert not llm_router.is_rate_limit_or_token_error(Exception(message))


# --------------------------------------------------
# LLM invocation and fallback tests
# --------------------------------------------------

def test_router_returns_first_successful_model(monkeypatch):
    calls = []

    class FakeLLM:
        def invoke(self, messages, config=None, **kwargs):
            calls.append(messages)
            return "hello"

    def fake_create_llm(model_config, temperature=0.0):
        return FakeLLM()

    monkeypatch.setattr(llm_router, "create_llm", fake_create_llm)

    model_router = llm_router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "model-a",
                "api_key_env": "GROQ_API_KEY",
            }
        ]
    )

    result = model_router.invoke("hi")

    assert result == "hello"
    assert calls == ["hi"]


def test_router_passes_temperature_and_config_to_model(monkeypatch):
    captured = {}

    class FakeLLM:
        def invoke(self, messages, config=None, **kwargs):
            captured["messages"] = messages
            captured["config"] = config
            captured["kwargs"] = kwargs
            return "response"

    def fake_create_llm(model_config, temperature=0.0):
        captured["temperature"] = temperature
        return FakeLLM()

    monkeypatch.setattr(llm_router, "create_llm", fake_create_llm)

    model_router = llm_router.LLMRouter(
        temperature=0.4,
        model_configs=[
            {
                "provider": "groq",
                "model": "model-a",
                "api_key_env": "GROQ_API_KEY",
            }
        ],
    )

    config = {"configurable": {"thread_id": "test-session"}}
    result = model_router.invoke(
        "hello",
        config=config,
        stop=["END"],
    )

    assert result == "response"
    assert captured["temperature"] == 0.4
    assert captured["messages"] == "hello"
    assert captured["config"] == config
    assert captured["kwargs"] == {"stop": ["END"]}


def test_router_falls_back_when_primary_hits_rate_limit(monkeypatch):
    attempted_models = []

    class FakeLLM:
        def __init__(self, model_name):
            self.model_name = model_name

        def invoke(self, messages, config=None, **kwargs):
            if self.model_name == "primary":
                raise Exception("429 rate limit")

            return "fallback response"

    def fake_create_llm(model_config, temperature=0.0):
        attempted_models.append(model_config["model"])
        return FakeLLM(model_config["model"])

    monkeypatch.setattr(llm_router, "create_llm", fake_create_llm)

    model_router = llm_router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "primary",
                "api_key_env": "GROQ_API_KEY",
            },
            {
                "provider": "openrouter",
                "model": "fallback",
                "api_key_env": "OPENROUTER_API_KEY",
            },
        ]
    )

    assert model_router.invoke("hi") == "fallback response"
    assert attempted_models == ["primary", "fallback"]


def test_router_raises_when_all_models_fail(monkeypatch):
    def fake_create_llm(model_config, temperature=0.0):
        raise Exception("429 rate limit")

    monkeypatch.setattr(llm_router, "create_llm", fake_create_llm)

    model_router = llm_router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "primary",
                "api_key_env": "GROQ_API_KEY",
            },
            {
                "provider": "openrouter",
                "model": "fallback",
                "api_key_env": "OPENROUTER_API_KEY",
            },
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="All configured LLM models failed",
    ):
        model_router.invoke("hi")


def test_router_does_not_fall_back_on_non_retryable_error(monkeypatch):
    attempted_models = []

    class FakeLLM:
        def invoke(self, messages, config=None, **kwargs):
            raise ValueError("invalid request")

    def fake_create_llm(model_config, temperature=0.0):
        attempted_models.append(model_config["model"])
        return FakeLLM()

    monkeypatch.setattr(llm_router, "create_llm", fake_create_llm)

    model_router = llm_router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "primary",
                "api_key_env": "GROQ_API_KEY",
            },
            {
                "provider": "openrouter",
                "model": "fallback",
                "api_key_env": "OPENROUTER_API_KEY",
            },
        ]
    )

    with pytest.raises(ValueError, match="invalid request"):
        model_router.invoke("hi")

    assert attempted_models == ["primary"]


# --------------------------------------------------
# Structured output tests
# --------------------------------------------------

def test_structured_output_converts_dictionary_to_schema(monkeypatch):
    class FakeStructuredLLM:
        def invoke(self, messages, config=None, **kwargs):
            return {"message": "Welcome"}

    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            assert schema is Reply
            return FakeStructuredLLM()

    monkeypatch.setattr(
        llm_router,
        "create_llm",
        lambda model_config, temperature=0.0: FakeLLM(),
    )

    model_router = llm_router.LLMRouter(
        structured_schema=Reply,
        model_configs=[
            {
                "provider": "groq",
                "model": "test-model",
                "api_key_env": "GROQ_API_KEY",
            }
        ],
    )

    result = model_router.invoke("hi")

    assert isinstance(result, Reply)
    assert result.message == "Welcome"


def test_structured_output_rejects_invalid_data(monkeypatch):
    class FakeStructuredLLM:
        def invoke(self, messages, config=None, **kwargs):
            return {"wrong_field": "invalid"}

    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            return FakeStructuredLLM()

    monkeypatch.setattr(
        llm_router,
        "create_llm",
        lambda model_config, temperature=0.0: FakeLLM(),
    )

    model_router = llm_router.LLMRouter(
        structured_schema=Reply,
        model_configs=[
            {
                "provider": "groq",
                "model": "test-model",
                "api_key_env": "GROQ_API_KEY",
            }
        ],
    )

    with pytest.raises(ValidationError):
        model_router.invoke("hi")


def test_structured_output_rejects_empty_response(monkeypatch):
    class FakeStructuredLLM:
        def invoke(self, messages, config=None, **kwargs):
            return None

    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            return FakeStructuredLLM()

    monkeypatch.setattr(
        llm_router,
        "create_llm",
        lambda model_config, temperature=0.0: FakeLLM(),
    )

    model_router = llm_router.LLMRouter(
        structured_schema=Reply,
        model_configs=[
            {
                "provider": "groq",
                "model": "test-model",
                "api_key_env": "GROQ_API_KEY",
            }
        ],
    )

    with pytest.raises(ValueError, match="groq returned an empty response"):
        model_router.invoke("hi")


def test_structured_output_kwargs_are_passed_to_model(monkeypatch):
    captured = {}

    class FakeStructuredLLM:
        def invoke(self, messages, config=None, **kwargs):
            return {"message": "Welcome"}

    class FakeLLM:
        def with_structured_output(self, schema, **kwargs):
            captured["schema"] = schema
            captured["kwargs"] = kwargs
            return FakeStructuredLLM()

    monkeypatch.setattr(
        llm_router,
        "create_llm",
        lambda model_config, temperature=0.0: FakeLLM(),
    )

    model_router = llm_router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "test-model",
                "api_key_env": "GROQ_API_KEY",
            }
        ],
    )

    structured_router = model_router.with_structured_output(
        Reply,
        method="json_schema",
    )
    result = structured_router.invoke("hi")

    assert isinstance(result, Reply)
    assert captured["schema"] is Reply
    assert captured["kwargs"] == {"method": "json_schema"}


def test_with_structured_output_returns_new_router_without_mutating_original():
    model_configs = [
        {
            "provider": "groq",
            "model": "test-model",
            "api_key_env": "GROQ_API_KEY",
        }
    ]

    base_router = llm_router.LLMRouter(model_configs=model_configs)
    structured_router = base_router.with_structured_output(
        Reply,
        method="json_schema",
    )

    assert isinstance(structured_router, llm_router.LLMRouter)
    assert structured_router is not base_router
    assert base_router.structured_schema is None
    assert structured_router.structured_schema is Reply
    assert structured_router.model_configs == model_configs
    assert structured_router.structured_output_kwargs == {
        "method": "json_schema"
    }


# --------------------------------------------------
# LLM router factory test
# --------------------------------------------------

def test_get_llm_returns_router(monkeypatch):
    model_configs = [
        {
            "provider": "groq",
            "model": "test-model",
            "api_key_env": "GROQ_API_KEY",
        }
    ]

    monkeypatch.setattr(
        llm_router,
        "load_model_configs",
        lambda: model_configs,
    )

    result = llm_router.get_llm(temperature=0.3)

    assert isinstance(result, llm_router.LLMRouter)
    assert result.temperature == 0.3
    assert result.model_configs == model_configs

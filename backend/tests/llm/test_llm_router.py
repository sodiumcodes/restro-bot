import pytest
from types import SimpleNamespace
from pydantic import BaseModel , ValidationError
from app.llm import llm_router as router

# A tiny pydantic schema used in the structured-output tests below.
# It represents the "shape" we expect the LLM to reply with.
class Reply(BaseModel):
    message: str

# --------------------------------------------------
# Model configuration tests
# These test load_model_configs(), which reads models.yaml
# --------------------------------------------------

def test_load_model_configs_prioritizes_primary_provider(
    monkeypatch, tmp_path
):
    # tmp_path is a temporary folder pytest creates (and deletes) for us,
    # so we can write a real YAML file without touching the project's files
    config_file = tmp_path / "models.yaml"

    # openrouter is listed FIRST in the file, groq second
    config_file.write_text(
        """
models:
  - provider: openrouter
    model: openrouter/model-a
    api_key_env: OPENROUTER_API_KEY

  - provider: groq
    model: groq-model
    api_key_env: GROQ_API_KEY
""",
        encoding="utf-8",
    )

    # Replace the real settings with a fake one that points to our temp file
    # and says groq is the primary provider
    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    configs = router.load_model_configs()

    # Even though groq was second in the file, it should now come first,
    # because it's the primary provider
    assert configs[0]["provider"] == "groq"
    assert configs[1]["provider"] == "openrouter"


def test_load_model_configs_rejects_empty_models(
    monkeypatch, tmp_path
):
    # A config file with an empty models list is invalid
    config_file = tmp_path / "models.yaml"
    config_file.write_text("models: []", encoding="utf-8")

    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    # The test passes only if a ValueError is raised AND its message
    # contains "non-empty models list"
    with pytest.raises(ValueError, match="non-empty models list"):
        router.load_model_configs()


def test_load_model_configs_rejects_unsupported_provider(
    monkeypatch, tmp_path
):
    # "gemini" is not a provider the router supports
    config_file = tmp_path / "models.yaml"

    config_file.write_text(
        """
models:
  - provider: gemini
    model: test-model
    api_key_env: API_KEY
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        router.load_model_configs()


def test_load_model_configs_rejects_missing_required_field(
    monkeypatch, tmp_path
):
    # This model entry is missing the required "api_key_env" field
    config_file = tmp_path / "models.yaml"

    config_file.write_text(
        """
models:
  - provider: groq
    model: test-model
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(config_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    # The error message should name the missing field
    with pytest.raises(ValueError, match="api_key_env"):
        router.load_model_configs()


def test_load_model_configs_file_not_found(monkeypatch, tmp_path):

    # Point the settings at a file that doesn't exist
    missing_file = tmp_path / "missing.yaml"

    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            LLM_MODELS_CONFIG=str(missing_file),
            PRIMARY_LLM_PROVIDER="groq",
        ),
    )

    # A missing config file should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        router.load_model_configs()


# --------------------------------------------------
# Model name resolution tests
# These test resolve_model_name(), which turns "${GROQ_MODEL}"
# style placeholders into real values from settings
# --------------------------------------------------

def test_resolve_model_name_from_settings(monkeypatch):

    # Fake settings that define GROQ_MODEL
    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            GROQ_MODEL="llama-test"
        ),
    )

    model = router.resolve_model_name({
        "provider": "groq",
        "model": "${GROQ_MODEL}",  # placeholder to be looked up in settings
        "api_key_env": "GROQ_API_KEY",
    })

    # The placeholder should be replaced by the value from settings
    assert model == "llama-test"


def test_resolve_model_name_without_placeholder():

    # No placeholder here, so no settings are needed
    model = router.resolve_model_name({
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "api_key_env": "GROQ_API_KEY",
    })

    # A plain model name should come back unchanged
    assert model == "openai/gpt-oss-120b"


def test_resolve_model_name_raises_for_missing_setting(
    monkeypatch
):

    # Empty settings: MISSING_MODEL is not defined anywhere
    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(),
    )

    # Using a placeholder that isn't in settings should raise a clear error
    with pytest.raises(ValueError, match="not configured"):
        router.resolve_model_name({
            "provider": "groq",
            "model": "${MISSING_MODEL}",
            "api_key_env": "GROQ_API_KEY",
        })


# --------------------------------------------------
# LLM initialization tests
# These test create_llm(), which builds the right client per provider
# --------------------------------------------------

def test_create_groq_llm(monkeypatch):

    # Dictionary that will record what create_llm passes to ChatGroq
    captured = {}

    # Fake ChatGroq: instead of making a real client, it saves the arguments
    # it received and returns a simple string
    def fake_chat_groq(**kwargs):
        captured.update(kwargs)
        return "fake-groq"

    # Swap the real ChatGroq in the router module for our fake
    monkeypatch.setattr(
        router,
        "ChatGroq",
        fake_chat_groq,
    )

    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            GROQ_API_KEY="test-key",
        ),
    )

    result = router.create_llm(
        {
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "api_key_env": "GROQ_API_KEY",
        },
        temperature=0.2,
    )

    # The function should return whatever ChatGroq returned...
    assert result == "fake-groq"
    # ...and should have passed the correct model, API key, and temperature
    assert captured["model"] == "openai/gpt-oss-120b"
    assert captured["api_key"] == "test-key"
    assert captured["temperature"] == 0.2


def test_create_openrouter_llm(monkeypatch):

    # Same idea as above, but OpenRouter uses ChatOpenAI with a custom base URL
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return "fake-openrouter"

    monkeypatch.setattr(
        router,
        "ChatOpenAI",
        fake_chat_openai,
    )

    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            OPENROUTER_API_KEY="test-key",
            OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
        ),
    )

    # No temperature given here, so the function's default is used
    result = router.create_llm(
        {
            "provider": "openrouter",
            "model": "nvidia/nemotron-3.5-super-vl:free",
            "api_key_env": "OPENROUTER_API_KEY",
        }
    )

    assert result == "fake-openrouter"
    assert captured["model"] == "nvidia/nemotron-3.5-super-vl:free"
    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"


def test_create_llm_raises_when_api_key_missing(monkeypatch):

    # GROQ_API_KEY exists in settings but has no value
    monkeypatch.setattr(
        router,
        "settings",
        SimpleNamespace(
            GROQ_API_KEY=None,
        ),
    )

    # Building an LLM without an API key should fail with a clear error
    with pytest.raises(ValueError, match="not configured"):
        router.create_llm({
            "provider": "groq",
            "model": "test-model",
            "api_key_env": "GROQ_API_KEY",
        })


# --------------------------------------------------
# Error detection tests
# These test is_rate_limit_or_token_error(), which decides
# whether an error should trigger a fallback to another model
# --------------------------------------------------

# parametrize runs this one test once for each message in the list,
# so we get 7 separate test cases from a single function
@pytest.mark.parametrize(
    "message",
    [
        "429 Too Many Requests",
        "rate limit reached",
        "insufficient_quota",
        "maximum context length exceeded",
        "tokens per minute exceeded",
        "resource has been exhausted",
        "overloaded",
    ],
)
def test_detects_rate_or_token_errors(message):

    # Every one of these messages should be recognized as a rate/token error
    assert router.is_rate_limit_or_token_error(
        Exception(message)
    )


def test_regular_error_is_not_rate_or_token_error():

    # An ordinary error should NOT be treated as a rate/token error
    assert not router.is_rate_limit_or_token_error(
        Exception("invalid request")
    )


# --------------------------------------------------
# LLM router invocation tests
# These test LLMRouter, which tries models in order
# and falls back to the next one on failure
# --------------------------------------------------

def test_router_returns_first_successful_model(monkeypatch):

    # Records each time a model is successfully invoked
    calls = []

    # A fake LLM whose invoke() always succeeds
    class FakeLLM:

        def invoke(self, messages, config=None, **kwargs):
            calls.append("success")
            return "hello"

    # Make create_llm return our fake instead of a real LLM client
    monkeypatch.setattr(
        router,
        "create_llm",
        lambda **kwargs: FakeLLM(),
    )

    llm_router = router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "model-a",
                "api_key_env": "KEY",
            },
        ]
    )

    # The router should return the model's answer, and call the model once
    assert llm_router.invoke("hi") == "hello"
    assert calls == ["success"]


def test_router_falls_back_when_primary_fails(monkeypatch):

    # Records which models create_llm was asked to build, in order
    calls = []

    class FakeLLM:

        def __init__(self, should_fail):
            self.should_fail = should_fail

        def invoke(self, messages, config=None, **kwargs):

            # The "primary" fake simulates a rate-limit error
            if self.should_fail:
                raise Exception("429 rate limit")

            return "fallback response"

    def fake_create_llm(model_config, temperature=0.0):

        # Note which model the router tried to use
        calls.append(model_config["model"])

        # Only the model named "primary" is set up to fail
        return FakeLLM(
            should_fail=model_config["model"] == "primary"
        )

    monkeypatch.setattr(
        router,
        "create_llm",
        fake_create_llm,
    )

    llm_router = router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "primary",
                "api_key_env": "KEY",
            },
            {
                "provider": "openrouter",
                "model": "fallback",
                "api_key_env": "KEY",
            },
        ]
    )

    # The primary fails, so the answer must come from the fallback model,
    # and both models must have been tried in the correct order
    assert llm_router.invoke("hi") == "fallback response"
    assert calls == ["primary", "fallback"]


def test_router_raises_when_all_models_fail(monkeypatch):

    # Here even creating the LLM fails, so no model can ever be used
    def fake_create_llm(model_config, temperature=0.0):
        raise Exception("429 rate limit")

    monkeypatch.setattr(
        router,
        "create_llm",
        fake_create_llm,
    )

    llm_router = router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "primary",
                "api_key_env": "KEY",
            },
        ]
    )

    # When every model fails, the router should raise one clear final error
    with pytest.raises(
        RuntimeError,
        match="All configured LLM models failed",
    ):
        llm_router.invoke("hi")


# --------------------------------------------------
# Structured output tests
# These test the router's ability to force replies into a pydantic schema
# --------------------------------------------------

def test_structured_output_is_validated(monkeypatch):

    # Fake "structured" LLM that returns a plain dict, like a real one might
    class FakeStructuredLLM:

        def invoke(self, messages, config=None, **kwargs):
            return {"message": "Welcome"}

    # Fake base LLM: the router should call with_structured_output() on it
    class FakeLLM:

        def with_structured_output(self, schema, **kwargs):

            # Check the router passed our Reply schema through
            assert schema is Reply

            return FakeStructuredLLM()

    monkeypatch.setattr(
        router,
        "create_llm",
        lambda **kwargs: FakeLLM(),
    )

    llm_router = router.LLMRouter(
        structured_schema=Reply,
        model_configs=[
            {
                "provider": "groq",
                "model": "test",
                "api_key_env": "KEY",
            },
        ],
    )

    result = llm_router.invoke("hi")

    # The router should turn the raw dict into a validated Reply object
    assert isinstance(result, Reply)
    assert result.message == "Welcome"


def test_with_structured_output_returns_new_router():

    llm_router = router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "test",
                "api_key_env": "KEY",
            },
        ],
    )

    # Ask for a structured version of the router, passing an extra option
    structured_router = llm_router.with_structured_output(
        Reply,
        method="json_schema",
    )

    # We should get a router back that remembers the schema and the options
    assert isinstance(structured_router, router.LLMRouter)
    assert structured_router.structured_schema is Reply
    assert structured_router.structured_output_kwargs == {
        "method": "json_schema"
    }

# --------------------------------------------------
# Router tests: regular (non rate-limit) errors
# --------------------------------------------------

def test_router_does_not_fall_back_on_regular_error(monkeypatch):
    # ASSUMPTION: only rate-limit / token errors trigger a fallback.
    # Any other error (like a bad request) is re-raised straight away,
    # because trying another model would just fail the same way.
    # If your router DOES fall back on every error, see the note after this file.

    # Records which models were actually called, in order
    calls = []

    class FakeLLM:

        def __init__(self, name):
            self.name = name

        def invoke(self, messages, config=None, **kwargs):
            # Note which model was called, then fail with a NON rate-limit error
            calls.append(self.name)
            raise Exception("invalid request")

    def fake_create_llm(model_config, temperature=0.0):
        # Give each fake LLM the name of its model so we can track it
        return FakeLLM(model_config["model"])

    monkeypatch.setattr(
        router,
        "create_llm",
        fake_create_llm,
    )

    llm_router = router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "first",
                "api_key_env": "KEY",
            },
            {
                "provider": "openrouter",
                "model": "second",
                "api_key_env": "KEY",
            },
        ]
    )

    # The original error should come out of invoke()
    with pytest.raises(Exception, match="invalid request"):
        llm_router.invoke("hi")

    # Only the first model was tried; the second was never touched
    assert calls == ["first"]


# --------------------------------------------------
# Structured output tests
# --------------------------------------------------

def test_structured_output_rejects_invalid_data(monkeypatch):

    # This fake LLM returns data that does NOT match the Reply schema:
    # it has "wrong_field" instead of the required "message" field
    class FakeStructuredLLM:

        def invoke(self, messages, config=None, **kwargs):
            return {"wrong_field": "oops"}

    class FakeLLM:

        def with_structured_output(self, schema, **kwargs):
            return FakeStructuredLLM()

    monkeypatch.setattr(
        router,
        "create_llm",
        lambda **kwargs: FakeLLM(),
    )

    llm_router = router.LLMRouter(
        structured_schema=Reply,
        model_configs=[
            {
                "provider": "groq",
                "model": "test",
                "api_key_env": "KEY",
            },
        ],
    )

    # Bad data must never be returned as if it were a valid Reply.
    # Depending on your router it surfaces either as pydantic's
    # ValidationError directly, or wrapped in the final RuntimeError
    # after every model has failed, so we accept either one.
    with pytest.raises((ValidationError, RuntimeError)):
        llm_router.invoke("hi")


def test_structured_output_kwargs_reach_the_llm(monkeypatch):

    # Dictionary that records what the underlying LLM was asked to do.
    # We record values here instead of using `assert` inside the fake,
    # so a failure gives a clear message instead of being swallowed
    # by the router's own error handling.
    captured = {}

    class FakeStructuredLLM:

        def invoke(self, messages, config=None, **kwargs):
            return {"message": "Welcome"}

    class FakeLLM:

        def with_structured_output(self, schema, **kwargs):
            # Save exactly what the router passed down to us
            captured["schema"] = schema
            captured["kwargs"] = kwargs
            return FakeStructuredLLM()

    monkeypatch.setattr(
        router,
        "create_llm",
        lambda **kwargs: FakeLLM(),
    )

    base_router = router.LLMRouter(
        model_configs=[
            {
                "provider": "groq",
                "model": "test",
                "api_key_env": "KEY",
            },
        ],
    )

    # Build the structured router with an extra option, then actually use it
    structured_router = base_router.with_structured_output(
        Reply,
        method="json_schema",
    )
    structured_router.invoke("hi")

    # The schema AND the extra option should have reached the real LLM
    assert captured["schema"] is Reply
    assert captured["kwargs"] == {"method": "json_schema"}


def test_with_structured_output_does_not_modify_original_router():

    model_configs = [
        {
            "provider": "groq",
            "model": "test",
            "api_key_env": "KEY",
        },
    ]

    base_router = router.LLMRouter(model_configs=model_configs)

    structured_router = base_router.with_structured_output(Reply)

    # It should be a brand new router, not the same object
    assert structured_router is not base_router

    # The original router must be left untouched (no schema added to it)
    assert base_router.structured_schema is None

    # The new router should still use the same models as the original
    assert structured_router.model_configs == model_configs
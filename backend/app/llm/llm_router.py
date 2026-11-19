
"""
LLM router for Cafe Chatbot.

Responsibilities:
- Load model fallback configuration from YAML.
- Initialize LLM providers.
- Support structured and normal LLM outputs.
- Detect rate limits and token limit errors.
- Automatically switch to fallback models.
"""

import logging
from pathlib import Path
from typing import Any, Type, TypeVar
import yaml
from pydantic import BaseModel
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from app.core.config import BASE_DIR, settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------
# Model configuration
# --------------------------------------------------

def load_model_configs() -> list[dict[str, str]]:
    """
    Load and validate model configurations from YAML.

    Models are attempted in the order specified in the file,
    with the primary provider given priority.
    """

    config_path = Path(settings.LLM_MODELS_CONFIG)

    if not config_path.is_absolute():
        config_path = BASE_DIR / "backend" / config_path

    if not config_path.exists():
        raise FileNotFoundError(
            f"LLM model configuration not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    models = config.get("models")

    if not isinstance(models, list) or not models:
        raise ValueError(
            "LLM configuration must contain a non-empty models list."
        )

    supported_providers = ("groq", "openrouter")

    for index, model_config in enumerate(models):

        if not isinstance(model_config, dict):
            raise ValueError(
                f"Invalid model configuration at index {index}."
            )

        required_fields = ("provider", "model", "api_key_env")

        for field in required_fields:
            if not model_config.get(field):
                raise ValueError(
                    f"Missing '{field}' in model configuration "
                    f"at index {index}."
                )

        provider = model_config["provider"].lower().strip()

        if provider not in supported_providers:
            raise ValueError(
                f"Unsupported LLM provider: {provider}"
            )

        model_config["provider"] = provider

    # Give the configured primary provider priority.
    primary_provider = settings.PRIMARY_LLM_PROVIDER.lower().strip()

    models.sort(
        key=lambda model: model["provider"] != primary_provider
    )

    return models


# --------------------------------------------------
# Model initialization
# --------------------------------------------------

def resolve_model_name(model_config: dict[str, str]) -> str:
    """
    Resolve model names from settings when YAML uses
    environment-style placeholders.
    """

    model_name = model_config["model"].strip()

    if model_name.startswith("${") and model_name.endswith("}"):
        setting_name = model_name[2:-1]
        model_name = getattr(settings, setting_name, None)

        if not model_name:
            raise ValueError(
                f"Model setting '{setting_name}' is not configured."
            )

    return str(model_name)


def create_llm(
    model_config: dict[str, str],
    temperature: float = 0.0,
):
    """
    Initialize an LLM using the configured provider and model.
    """

    provider = model_config["provider"]
    model_name = resolve_model_name(model_config)
    api_key_name = model_config["api_key_env"]

    api_key = getattr(settings, api_key_name, None)

    if not api_key:
        raise ValueError(
            f"{api_key_name} is not configured."
        )

    if provider == "groq":

        return ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
        )

    elif provider == "openrouter":

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=temperature,
        )

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )


# --------------------------------------------------
# Error detection
# --------------------------------------------------

def is_rate_limit_or_token_error(exception: Exception) -> bool:
    """
    Check whether an exception is related to rate limits,
    quota limits, or token window exhaustion.
    """

    message = str(exception).lower()

    keywords = [
        "rate limit",
        "ratelimit",
        "429",
        "quota",
        "token limit",
        "tokens per minute",
        "tpm",
        "rpm",
        "context length",
        "context window",
        "maximum context",
        "insufficient_quota",
        "resource has been exhausted",
        "overloaded",
    ]

    return any(
        keyword in message
        for keyword in keywords
    )


# --------------------------------------------------
# LLM execution router
# --------------------------------------------------

class LLMRouter:
    """
    Handles LLM execution with automatic model fallback.

    Supports:
    - Normal text generation.
    - Pydantic structured output.
    - Multiple providers and models.
    """

    def __init__(
        self,
        temperature: float = 0.0,
        structured_schema: Type[T] | None = None,
        model_configs: list[dict[str, str]] | None = None,
        structured_output_kwargs: dict[str, Any] | None = None,
    ) -> None:

        self.temperature = temperature
        self.structured_schema = structured_schema

        self.model_configs = (
            model_configs
            if model_configs is not None
            else load_model_configs()
        )

        self.structured_output_kwargs = (
            structured_output_kwargs or {}
        )

    # ----------------------------------------------
    # Structured output
    # ----------------------------------------------

    def with_structured_output(
        self,
        schema: Type[T],
        **kwargs: Any,
    ) -> "LLMRouter":
        """
        Return a router configured for Pydantic structured output.

        Keeps fallback functionality when structured output is used.
        """

        return LLMRouter(
            temperature=self.temperature,
            structured_schema=schema,
            model_configs=self.model_configs,
            structured_output_kwargs=kwargs,
        )

    # ----------------------------------------------
    # LLM invocation
    # ----------------------------------------------

    def invoke(
        self,
        messages: Any,
        config: Any = None,
        **kwargs: Any,
    ) -> Any:
        """
        Execute an LLM request using the configured fallback order.

        If a model fails, the next available model is attempted.
        """

        last_error = None

        for model_config in self.model_configs:

            provider = model_config["provider"]

            try:
                model_name = resolve_model_name(model_config)

                logger.info(
                    f"Trying LLM: {provider} / {model_name}"
                )

                # Initialize the configured model.
                llm = create_llm(
                    model_config=model_config,
                    temperature=self.temperature,
                )

                # Apply structured output when a schema is provided.
                if self.structured_schema is not None:

                    llm = llm.with_structured_output(
                        self.structured_schema,
                        **self.structured_output_kwargs,
                    )

                # Execute the request.
                result = llm.invoke(
                    messages,
                    config=config,
                    **kwargs,
                )

                # Validate the structured response.
                if self.structured_schema is not None:

                    if result is None:
                        raise ValueError(
                            f"{provider} returned an empty response."
                        )

                    if not isinstance(
                        result,
                        self.structured_schema,
                    ):
                        result = self.structured_schema.model_validate(
                            result
                        )

                logger.info(
                    f"LLM request successful: {provider} / {model_name}"
                )

                return result

            except Exception as exc:

                last_error = exc

                is_limit_error = is_rate_limit_or_token_error(exc)

                logger.warning(
                    f"LLM failed: {provider}. "
                    f"Model: {model_config['model']}. "
                    f"Rate/token limit: {is_limit_error}. "
                    f"Error: {exc}"
                )

                # Stop immediately if the error is not retryable.
                if not is_limit_error:
                    raise

                logger.info(
                    "Rate/token limit reached. "
                    "Switching to the next configured LLM model."
                )

                continue

        raise RuntimeError(
            "All configured LLM models failed. "
            f"Last error: {last_error}"
        ) from last_error


# --------------------------------------------------
# Router factory
# --------------------------------------------------

def get_llm(
    temperature: float = 0.0,
) -> LLMRouter:
    """
    Create and return an LLM router.

    The actual provider is initialized when invoke() is called.
    """

    return LLMRouter(
        temperature=temperature,
    )

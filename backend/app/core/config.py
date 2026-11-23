from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Locate the project root.
# config.py -> core -> app -> backend -> project root
BASE_DIR = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):

    # Application settings
    APP_NAME: str = "Cafe Chatbot"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str
    # Frontend configuration
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # API configuration
    MAX_MESSAGE_LENGTH: int = 500
    CART_MAX_QUANTITY: int = 10

    # Rate limiting configuration
    CHAT_RATE_LIMIT: str = "10/minute"
    SESSION_RATE_LIMIT: str = "5/minute"

    # Data retention
    RETENTION_DAYS: int = 30

    # Embedding configuration
    EMBEDDING_PROVIDER: str 
    EMBEDDING_MODEL: str 
    EMBEDDING_DIM: int = 2048
    EMBEDDING_BATCH_SIZE: int = 10
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # LLM router configuration
    LLM_MODELS_CONFIG: str = "app/config/llm_models.yaml"
    LLM_TEMPERATURE: float = 0.0
    LLM_MAX_RETRIES: int = 2
    PRIMARY_LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str | None = None
    STAFF_API_KEY: str | None = None

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / "backend" / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

# Create one settings instance for the application
settings = Settings()

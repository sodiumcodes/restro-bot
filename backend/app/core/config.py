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

    # Pydantic settings configuration
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Create one settings instance for the application
settings = Settings()

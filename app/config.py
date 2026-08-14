from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Vehicle Service Shop API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: Literal["development", "testing", "production", "staging"] = "development"

    # Database Settings
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/vehicle_service_shop"
    )
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800  # Recycle connections after 30 minutes to prevent stale TCP sockets

    # JWT Security Settings
    SECRET_KEY: str  # Mandatory! No default to force configuration.
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # 15 minutes access token lifetime
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MIN_PASSWORD_LENGTH: int = 8

    # Rate Limiting
    RATE_LIMIT_AUTH: int = 10  # Max requests per minute for auth routes

    # Tax Settings
    TAX_RATE: float = 0.07  # 7% default - override via .env
    TAX_LABEL: str = "Sales Tax"

    # Shop Identity (for PDF headers & receipts)
    SHOP_NAME: str = "Auto Service Shop"
    SHOP_ADDRESS: str = "123 Main Street, City, ST 12345"
    SHOP_PHONE: str = "(555) 555-0100"

    # Email / SMTP Settings
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@autoserviceshop.com"
    SMTP_FROM_NAME: str = "Auto Service Shop"
    SMTP_USE_TLS: bool = True
    EMAIL_ENABLED: bool = False  # Disabled by default; enable via .env in production

    # File Upload Settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10
    MAX_FILES_PER_ENTITY: int = 5
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,gif,webp,pdf,doc,docx"

    # Stripe Payment Gateway Settings
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_ENABLED: bool = False
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/payment/success?session_id={CHECKOUT_SESSION_ID}"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/payment/cancel"

    # CORS Settings
    CORS_ORIGINS: str = "http://localhost:3000"

    # Default Seed Admin Credentials
    SEED_ADMIN_USERNAME: str = "admin"
    SEED_ADMIN_EMAIL: str = "admin@autoserviceshop.com"
    SEED_ADMIN_PASSWORD: str = "ChangeMe123!"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL (e.g., postgresql+asyncpg://...)")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        if not v.strip():
            return "http://localhost:3000"
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = Field(default="development", description="development, staging, production")

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://mydeliverys:changeme@localhost:6432/mydeliverys",
        description="PostgreSQL connection URL via PgBouncer",
    )
    DATABASE_POOL_MIN_SIZE: int = Field(default=10, description="Min connections per worker")
    DATABASE_POOL_MAX_SIZE: int = Field(default=25, description="Max connections per worker")

    # Redis
    REDIS_CONTROL_URL: str = Field(
        default="redis://localhost:6379/0", description="Redis sin eviction para controles"
    )
    REDIS_CACHE_URL: str = Field(
        default="redis://localhost:6380/0", description="Redis evictable para cache"
    )
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/2")

    # Security / JWT
    SECRET_KEY: str = Field(
        default="dev-secret-change-in-production-please-use-strong-key", REDACTED
    )
    CREDENTIAL_ENCRYPTION_SECRET: str = Field(
        default="dev-credential-encryption-secret-change-me", REDACTED
    )
    JWT_ALGORITHM: str = Field(default="RS256")
    JWT_PRIVATE_KEY_PATH: str = Field(default="./keys/private.pem")
    JWT_PUBLIC_KEY_PATH: str = Field(default="./keys/public.pem")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=30)
    WEB_SESSION_MAX_HOURS: int = Field(default=8)
    PASSWORD_HASH_ALGORITHM: str = Field(default="argon2id")

    # OTP / WhatsApp
    OTP_TTL_SECONDS: int = Field(default=180)
    OTP_MAX_ATTEMPTS: int = Field(default=3)
    OTP_BLOCK_MINUTES: int = Field(default=10)
    OTP_IP_MAX_REQUESTS: int = Field(default=5)
    OTP_IP_WINDOW_MINUTES: int = Field(default=3)
    WHATSAPP_API_URL: str | None = Field(default=None)
    WHATSAPP_API_TOKEN: str | None = Field(default=None)
    WHATSAPP_PHONE_NUMBER_ID: str | None = Field(default=None)

    # Exchange Rate (DolarAPI Venezuela)
    DOLARAPI_URL: str = Field(default="https://ve.dolarapi.com/v1/dolares/oficial")
    EXCHANGE_RATE_FETCH_INTERVAL_MINUTES: int = Field(default=30)
    EXCHANGE_RATE_STALE_HOURS: int = Field(default=6)

    # Inventory / Reservations
    RESERVATION_TTL_MINUTES: int = Field(default=15)

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(default=True)

    # CORS
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080", "capacitor://localhost"]
    )

    # FCM / Push
    FCM_CREDENTIALS_PATH: str | None = Field(default=None)

    # Logging
    LOG_LEVEL: str = Field(default="INFO")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

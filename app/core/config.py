from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str
    APP_URL: str = "http://localhost:8000"
    JWT_SECRET: str
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_GROWTH: str = ""
    GEMINI_API_KEY: str
    RESEND_API_KEY: str
    SENTRY_DSN: str = ""


settings = Settings()

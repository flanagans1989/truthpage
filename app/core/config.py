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
    PADDLE_API_KEY: str = ""
    PADDLE_CLIENT_TOKEN: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    PADDLE_PRICE_ID_GROWTH: str = ""
    PADDLE_ENVIRONMENT: str = "sandbox"  # "sandbox" | "production"
    GEMINI_API_KEY: str
    RESEND_API_KEY: str
    RESEND_FROM_EMAIL: str = "TrustPages <onboarding@resend.dev>"
    SENTRY_DSN: str = ""
    # Growth plan cap; raise per-tenant later if plans diversify
    MAX_SUBPROCESSORS_PER_TENANT: int = 25
    # Comma-separated emails allowed to open /admin (matched against tenant.email)
    ADMIN_EMAILS: str = ""

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip())


settings = Settings()

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
    PADDLE_PRICE_ID_GROWTH_YEARLY: str = ""
    # Starter is the middle tier. Blank until a real Paddle price exists for
    # it — checkout treats a blank price id as "not configured yet" the same
    # way it already does for Growth, so this ships safely ahead of Paddle
    # being set up: the pricing page can describe the tier before anyone can
    # actually buy it.
    PADDLE_PRICE_ID_STARTER: str = ""
    PADDLE_PRICE_ID_STARTER_YEARLY: str = ""
    PADDLE_ENVIRONMENT: str = "sandbox"  # "sandbox" | "production"
    GEMINI_API_KEY: str
    RESEND_API_KEY: str
    RESEND_FROM_EMAIL: str = "TrustPages <onboarding@resend.dev>"
    SENTRY_DSN: str = ""
    # GA4 measurement ID (e.g. "G-XXXXXXX"); blank disables analytics
    GA_MEASUREMENT_ID: str = ""
    # Growth plan cap.
    MAX_SUBPROCESSORS_PER_TENANT: int = 30
    # Starter plan cap — the middle tier between free and Growth.
    STARTER_MAX_SUBPROCESSORS: int = 10
    # Permanent free plan. Every free tenant still costs a scrape per page per
    # day, so this is a compute knob as much as a packaging one — see the sweep
    # note in CLAUDE.md before raising it.
    FREE_TIER_MAX_SUBPROCESSORS: int = 3
    # Comma-separated emails allowed to open /admin (matched against tenant.email)
    ADMIN_EMAILS: str = ""

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip())


settings = Settings()

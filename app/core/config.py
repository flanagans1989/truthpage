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

    # A source is flagged with a persistent "Monitoring Alert" once its
    # consecutive failed checks (4xx/5xx, timeout, empty content) reach this.
    MONITORING_ALERT_FAILURE_THRESHOLD: int = 3
    # Once the alert email fires for a source, don't fire it again for this
    # many days even if it keeps failing — a page that's been down a week
    # doesn't need a fresh email every single day.
    MONITORING_ALERT_DEDUPE_DAYS: int = 7

    # Tier-2 (Playwright) runs are the expensive path — a real browser launch,
    # not an httpx GET. These are per-tenant, per-UTC-day ceilings on how many
    # Tier-2 runs a tenant's already-bot-walled sources may consume; going over
    # queues the check for the next day rather than skipping it silently.
    TIER2_DAILY_LIMIT_FREE: int = 3
    TIER2_DAILY_LIMIT_STARTER: int = 10
    TIER2_DAILY_LIMIT_GROWTH: int = 30

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip())


settings = Settings()

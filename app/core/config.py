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
    # consecutive failed checks (4xx/5xx, timeout, empty content, bot wall)
    # reach this, OR once it's simply gone stale — see STALENESS_ALERT_DAYS.
    MONITORING_ALERT_FAILURE_THRESHOLD: int = 3
    # Once an alert email fires for a source, don't fire the same alert again
    # for this many days even if the condition persists — resends again after
    # this window if still unresolved (see monitoring.py); cleared entirely on
    # recovery so a later, unrelated occurrence alerts immediately.
    MONITORING_ALERT_DEDUPE_DAYS: int = 7
    # Independent of the failure counter above: a source not successfully
    # checked in this many days alerts regardless of *why* — a failure
    # streak, a long Tier-2 budget deferral, a dropped worker, anything.
    # The failure counter answers "is it erroring"; this answers "has it
    # actually been looked at" — a budget deferral trips this with zero
    # recorded failures.
    STALENESS_ALERT_DAYS: int = 3

    # Tier-2 (Playwright) runs are the expensive path — a real browser launch,
    # not an httpx GET. TIER2_DAILY_PER_SOURCE is the real cost control: each
    # already-bot-walled source may run Tier-2 at most this many times per UTC
    # day. TIER2_DAILY_LIMIT_{FREE,STARTER,GROWTH} is a separate, tenant-wide
    # SAFETY VALVE (not a feature tier) sized well above what per-source quotas
    # should ever add up to — see Tenant.tier2_daily_limit and
    # app/services/tier2_budget.py. Either cap queues the check rather than
    # skipping it silently.
    TIER2_DAILY_PER_SOURCE: int = 2
    TIER2_DAILY_LIMIT_FREE: int = 6
    TIER2_DAILY_LIMIT_STARTER: int = 20
    TIER2_DAILY_LIMIT_GROWTH: int = 60

    # Below this many characters of normalized, visible text, a fetched page
    # is treated as unhealthy (a bot-wall interstitial, an empty shell, a
    # script-only render) rather than as real content — never stored as a
    # snapshot, never diffed. See app/core/scraper/content_health.py.
    CONTENT_HEALTH_MIN_TEXT_LENGTH: int = 500

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip())


settings = Settings()

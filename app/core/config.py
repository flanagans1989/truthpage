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
    # Resend's per-endpoint signing secret ("whsec_...") for /webhooks/resend
    # — see app/routers/webhooks.py. Same purpose as PADDLE_WEBHOOK_SECRET
    # above: without it, anyone could POST a fabricated "delivered" event.
    RESEND_WEBHOOK_SECRET: str = ""
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
    # Google's Gemini free tier caps requests per minute for the whole
    # account, not per code path — every classifier/extractor/drafter in
    # this app shares one quota. Hit in production (Sentry TRUSTPAGES-8,
    # 2026-09-02): "Quota exceeded ... limit: 5" during a directory sweep
    # tick with several vendor pages due at once, each good for up to two
    # calls (diff classification + entry extraction). See
    # app/core/llm/rate_limit.py, which every Gemini call site awaits
    # before calling the API, so this number is the one place that caps
    # them all. Raise it only after moving off the free tier.
    GEMINI_FREE_TIER_RPM: int = 5
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

    # Shared secret for POST /internal/sweep. Deliberately NOT JWT_SECRET:
    # that key signs login sessions, and a manual sweep trigger is a far
    # lower-trust thing to hand to a cron provider, a status page, or a
    # teammate. One secret for both meant leaking the cron header also
    # meant forging any user's session. Blank disables the endpoint
    # entirely (503) rather than silently falling back to JWT_SECRET —
    # a fallback would quietly re-create the coupling this removes.
    SWEEP_SECRET: str = ""
    # Honour robots.txt for the PUBLIC VENDOR DIRECTORY only — pages we
    # crawl on our own initiative, with no customer relationship and all
    # the exposure on us. Tenant-monitored URLs are fetched on a
    # customer's instruction under the Terms and are not gated on this;
    # see app/core/scraper/robots.py for the reasoning.
    RESPECT_ROBOTS_TXT: bool = True
    # GET /healthz/monitoring reports "degraded" once the last COMPLETED
    # sweep is older than this. The scheduler ticks every 3 hours (see
    # app/main.py), so this is three missed ticks plus slack: long enough
    # that one slow cycle is not an alarm, short enough that a dead
    # scheduler is caught the same day.
    SWEEP_MAX_AGE_HOURS: float = 10.0
    # Grace period after process start before a missing heartbeat counts
    # as degraded. A fresh deploy has no completed sweep yet and must not
    # fail its own probe on the way up.
    SWEEP_BOOT_GRACE_MINUTES: float = 20.0

    # RFC 3161 timestamping — see app/core/tsa.py and app/services/tsa_retry.py.
    # FreeTSA only for now (see docs/manifest_v2.md); TSA_FALLBACK_URL stays
    # blank until a second provider's CA chain is sourced and bundled — do not
    # set this without also adding that chain file, or a fallback-issued
    # token becomes unverifiable offline.
    TSA_PRIMARY_URL: str = "https://freetsa.org/tsr"
    TSA_FALLBACK_URL: str = ""
    TSA_TIMEOUT_SECONDS: float = 20.0
    TSA_MAX_ATTEMPTS: int = 5

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

    # Fallback used only where Tenant.objection_window_days hasn't been
    # explicitly set otherwise (i.e. new tenants, via the column's own
    # server_default) — see docs/manifest_v2.md's [OBJECTION WINDOW]
    # section. Never read directly to decide an actual window; that always
    # comes from the tenant's own row.
    DEFAULT_OBJECTION_WINDOW_DAYS: int = 30

    @property
    def admin_email_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip())


settings = Settings()

# TrustPages

Privacy policy sub-processor monitoring SaaS. Tenants add URLs to monitor; the app scrapes them every N minutes, diffs HTML, classifies changes via Gemini as MATERIAL/COSMETIC/UNCERTAIN, auto-publishes cosmetic changes, queues material ones for manual approval, and notifies email subscribers.

## Stack

- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL (Neon)
- **Templates:** Jinja2 + HTMX + Tailwind CDN
- **LLM:** Gemini 2.5 Flash (`google-genai`)
- **Scheduler:** APScheduler (5-min sweep)
- **Auth:** Magic link → JWT cookie (30-day session)
- **Billing:** Paddle (Merchant of Record — Stripe doesn't support Turkey-based sellers)
- **Email:** Resend
- **Deploy:** Render (render.yaml; migrations run via preDeployCommand)
- **Package manager:** uv

## Key files

```
app/main.py                  # FastAPI app + scheduler startup
app/core/config.py           # Settings (pydantic-settings, reads .env)
app/core/llm/analyzer.py     # Gemini diff classification
app/core/scraper/            # fetcher (httpx+Playwright), normalizer, hasher, detector
app/services/monitoring.py   # Sweep orchestration: fetch→normalize→hash→diff→LLM→persist
app/scheduler/jobs.py        # APScheduler job (calls monitoring.py)
app/routers/                 # auth, dashboard, subprocessors, billing, webhooks, public
app/db/models/               # Tenant, Subprocessor, ChangeEvent, Subscriber
```

## Commands

```bash
uv run uvicorn app.main:app --reload   # local dev
alembic upgrade head                   # run migrations
python run_sweep.py                    # manual sweep trigger
```

## Required env vars

`DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`, `RESEND_API_KEY`, `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_ID_GROWTH`, `APP_URL`  
Optional: `SENTRY_DSN`

## Business logic

- **Auto-publish:** `classification == COSMETIC && confidence > 0.85` → `ChangeStatus.auto_published`
- **Manual review:** everything else → `ChangeStatus.pending_review`
- **Diff cap:** 12 000 chars sent to LLM (~3k tokens)
- **Scraper tiers:** Tier-1 httpx; Tier-2 Playwright fallback (per `subprocessor.requires_browser`)
- **Rate limit:** 3 magic link requests / minute per IP and per email
- **DB pool:** `pool_size=3, max_overflow=1` (Neon free tier)
- **Subscription statuses:** `trialing | active | past_due | canceled | unpaid`
- **Trial:** 14 days (`tenant.trial_ends_at`); expired trials are excluded from sweeps and redirected to checkout on login
- **Auth:** tenant ↔ email is exact-match (`tenant.email`, unique); magic links are single-use
- **Tenant alerts:** pending-review changes email the tenant owner (`mailer.send_review_needed`)
- **Plan cap:** `MAX_SUBPROCESSORS_PER_TENANT` (default 25)
- **Public trust page:** shows approved + auto-published change history (last 20)
- **Tests:** `uv run pytest` (unit tests, no DB needed); CI via GitHub Actions

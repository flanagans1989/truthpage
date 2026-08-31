# TrustPages

Privacy policy sub-processor monitoring SaaS. Tenants add URLs to monitor; the app scrapes them every N minutes, diffs HTML, classifies changes via Gemini as MATERIAL/COSMETIC/UNCERTAIN, auto-publishes cosmetic changes, queues material ones for manual approval, and notifies email subscribers.

## Stack

- **Backend:** FastAPI + SQLAlchemy async + PostgreSQL (Neon)
- **Templates:** Jinja2 + HTMX + Tailwind CDN
- **LLM:** Gemini 2.5 Flash (`google-genai`)
- **Scheduler:** APScheduler (3-hour sweep — every tick wakes the Neon compute for its 5-min scale-to-zero window, so tick frequency, not work done, drives the bill. 30-min ticks burned ~124 compute-hours/month against a 100-hour free-tier cap and took the site down for a week on 2026-08-24; see incidents 2026-07-19 and 2026-08-31. Do not shorten this without re-doing the arithmetic.)
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
app/core/templating.py       # Shared Jinja2Templates instance (injects ga_measurement_id global)
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

# Rebuild compiled CSS after any template/class change (CLI vendored in tools/, gitignored):
./tools/tailwindcss.exe -o static/tailwind.css --minify --content "./templates/**/*.html,./app/**/*.py"
```

## Claude Code GitHub integration

`.github/workflows/claude.yml` runs the official `anthropics/claude-code-action` — mention
`@claude` in an issue (title/body) or PR/issue comment to have Claude pick up the task and push
commits/open a PR. Auth: repo secret `ANTHROPIC_API_KEY` (or `CLAUDE_CODE_OAUTH_TOKEN` for a
subscription token — swap the input name in the workflow if used instead). Requires the
[Claude GitHub App](https://github.com/apps/claude) installed on the repo.

## Required env vars

`DATABASE_URL`, `JWT_SECRET`, `GEMINI_API_KEY`, `RESEND_API_KEY`, `PADDLE_API_KEY`, `PADDLE_CLIENT_TOKEN`, `PADDLE_WEBHOOK_SECRET`, `PADDLE_PRICE_ID_GROWTH`, `APP_URL`  
Optional: `SENTRY_DSN`, `GA_MEASUREMENT_ID` (GA4, e.g. `G-XXXXXXX` — blank disables analytics)

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

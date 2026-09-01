# TrustPages

Sub-processor monitoring SaaS. Tenants add vendor policy URLs; a sweep scrapes → diffs → Gemini
classifies MATERIAL/COSMETIC/UNCERTAIN → cosmetic auto-publishes, material queues for approval →
subscribers get email.

FastAPI · async SQLAlchemy · Postgres (Neon free tier) · Jinja2/HTMX · Gemini 2.5 Flash ·
APScheduler · Paddle (MoR — Stripe won't take Turkey-based sellers) · Resend · Render · uv

## Commands

```bash
uv run uvicorn app.main:app --reload   # dev
uv run pytest                          # tests, no DB needed
python run_sweep.py                    # manual sweep
./tools/tailwindcss.exe -o static/tailwind.css --minify --content "./templates/**/*.html,./app/**/*.py"
```

## Traps

- **Sweep interval is a billing knob, not a latency knob.** Every tick wakes the Neon compute for
  its 5-min scale-to-zero window whether or not work is due. 30-min ticks burn ~124 compute-hours
  a month against a 100-hour cap — that took the site down for a week (2026-08-24). It is 3h now.
  Don't shorten it without redoing the arithmetic.
- **CSS is compiled, not CDN.** Rerun the Tailwind command above after any class change, and note
  it scans `app/**/*.py` too because routers contain inline HTML.
- **`preDeployCommand` is silently ignored on Render free.** Migrations run from the Dockerfile
  `CMD` (`alembic upgrade head && uvicorn ...`). Moving them back breaks production silently.
- **Chromium is COPYed from `mcr.microsoft.com/playwright:<ver>`** because cdn.playwright.dev
  geo-blocks Render's builder. Bump that tag whenever playwright is upgraded.
- **Use the shared `templates` from `app/core/templating.py`** — it injects the
  `ga_measurement_id` global. A router that builds its own `Jinja2Templates` loses it.
- **`RESEND_FROM_EMAIL` must be on a Resend-verified domain.** `onboarding@resend.dev` is a
  shared sandbox sender that only delivers to the account owner — magic links to yourself work,
  so it looks fine while every subscriber notification is dropped. Set it in the Render
  dashboard too; `render.yaml` alone did not take effect.

## Rules that aren't visible in a quick read

- Auto-publish iff `COSMETIC && confidence > 0.85`; everything else → `pending_review`
- Diff sent to the LLM is capped at 12 000 chars
- Tier-1 httpx, Tier-2 Playwright per `subprocessor.requires_browser`
- Trial is 14 days; expired tenants are skipped by sweeps and bounced to checkout at login
- tenant ↔ email is exact-match and unique; magic links are single-use, 3/min per IP and per email
- DB pool `size=3, overflow=1` (Neon free tier)
- Plan cap `MAX_SUBPROCESSORS_PER_TENANT`, default 25
- Public trust page shows the last 20 approved + auto-published changes

Env vars: see `.env.example`. `SENTRY_DSN` and `GA_MEASUREMENT_ID` are optional.

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
- **`render.yaml` is not a mirror of production.** Values there are the blueprint's, not what
  the service actually runs: `RESEND_FROM_EMAIL` read `onboarding@resend.dev` in the file while
  the dashboard had `noreply@usetrustpages.com`. Reveal the dashboard value before concluding
  anything about production from this file.
- **`run_sweep.py` must be run, never imported.** Its `asyncio.run(main())` is now behind a
  `__main__` guard because importing the module ran a real sweep against the `.env` DATABASE_URL
  — which points at production.
- **`RESEND_FROM_EMAIL` must be on a Resend-verified domain** (`usetrustpages.com`).
  `onboarding@resend.dev` is a shared sandbox sender that only delivers to the account owner, so
  magic links to yourself would still work while every subscriber notification is dropped.

## Rules that aren't visible in a quick read

- Auto-publish iff `COSMETIC && confidence > 0.85`; everything else → `pending_review`
- Diff sent to the LLM is capped at 12 000 chars
- Tier-1 httpx, Tier-2 Playwright per `subprocessor.requires_browser`
- Trial is 14 days; on expiry the tenant drops to the free plan (see below), keeps signing in
- tenant ↔ email is exact-match and unique; magic links are single-use, 3/min per IP and per email
- DB pool `size=3, overflow=1` (Neon free tier)
- Plan cap `MAX_SUBPROCESSORS_PER_TENANT`, default 25; free plan `FREE_TIER_MAX_SUBPROCESSORS`,
  default 3 — read the sweep-interval trap above before raising it, every free tenant costs a
  scrape per page per day
- A subscription that ends becomes `subscription_status="free"`, never a dead account: an
  expired trial at the top of each sweep tick, a cancellation via the Paddle webhook. Both go
  through `services.plans.move_tenant_to_free`, which disables pages above the free cap
  (oldest kept) without deleting them. Tenants in `ADMIN_EMAILS` are exempt from the trial
  path — that tenant is the showcase trust page
- Article 28(2) notice drafts are stored on the change event and only redrawn on request; the
  tenant may already have sent the earlier wording
- **A trust page is 404 until `tenants.onboarded_at` is set.** The onboarding wizard's Publish
  button is what sets it; migration 0011 backfilled every pre-wizard tenant to `created_at` so
  no live page went dark. `/trust/{slug}` and its subscribe endpoint both check it — a list
  someone is halfway through building is not something to hand a crawler
- **A new signup lands on `/onboarding`, not on the checkout form.** The trial is already
  running; asking for a card before they have seen a page was the step that lost them.
  `tenant.needs_onboarding` (i.e. `onboarded_at IS NULL`) is what routes them
- The 32 providers in `app/core/provider_library.py` carry a `verified` flag, and it means one
  thing: the public directory sweep has actually read a sub-processor list off that URL. Do not
  set it by eye. Monogram tiles, not hotlinked logos — third-party image requests from the
  dashboard, and trademark use we don't need
- The policy importer never guesses a monitoring URL from a name. A name it cannot match in the
  library comes back as "give us the URL"; `match_provider` is alias + normalised-name only, no
  fuzzy distance, because a near-miss silently monitors the wrong company's page
- The importer fetches Tier-1 only (`fetch_html_fast`) — a human is waiting on that request, and
  a cold Playwright escalation takes longer than they will wait. A bot wall becomes "paste the
  text instead", which is faster than the escalation would have been
- `/compare` describes competitor *categories*, never names: naming a rival our own size on our
  own site advertises them. Figures are ranges in `app/core/comparisons.py` with a `VERIFIED_ON`
  date shown on the page — update the date and the numbers together. A test asserts no competitor
  name appears in the copy. The old `/vs/{slug}` URLs 301 to `/compare`
- Public trust page shows the last 20 approved + auto-published changes, and carries a
  "Powered by TrustPages" badge with UTM parameters. `tenants.hide_powered_by` removes it, but
  only while `may_hide_badge` (i.e. not on the free plan) — a downgrade restores the badge
  without a cleanup job
- **The directory (`vendors`) is not the tenant `subprocessors` table.** One canonical page per
  vendor, monitored by the platform, published to everyone. Rows are inserted unpublished by
  `seed_vendors.py` and become public only when a check reads a list off the page, so a wrong
  seed URL costs a failed fetch, never a broken public page
- Vendor entries come from a Gemini extraction pass per detected change (`llm/extractor.py`);
  `diff_entries` compares names only, so a reworded purpose column is not reported as an addition
- `fetch_raw_html` takes an `on_escalate` callback for the Tier-2 escalation write — it does not
  know whether a URL belongs to a subprocessor or a vendor

Env vars: see `.env.example`. `SENTRY_DSN` and `GA_MEASUREMENT_ID` are optional.

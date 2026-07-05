# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Use /app so venv shebang paths match the runtime stage exactly
WORKDIR /app

# Inject uv from the official image (no pip needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Layer-cache: sync dependencies before copying application code
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY . .
RUN uv sync --frozen --no-dev

# ── Stage 2: browser binaries ────────────────────────────────────────────────
# cdn.playwright.dev geo-blocks Render's build region (403 "not available in
# your location"), so `playwright install` fails there. Take the browsers from
# Microsoft's official image instead — tag MUST match the locked playwright
# version in uv.lock. Drop the browsers we don't use to keep the image small.
FROM mcr.microsoft.com/playwright:v1.60.0-noble AS browsers
RUN rm -rf /ms-playwright/firefox-* /ms-playwright/webkit-*

# ── Stage 3: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Bring uv and the full virtualenv from the builder first so that
# `playwright install-deps` can resolve the correct system packages
# for whatever Debian version this base image ships (avoids hardcoding
# package names that change across Debian releases, e.g. libasound2 → libasound2t64).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=builder /app /app

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

# System libraries via apt (no CDN involved), browser binaries from the MCR image
RUN uv run playwright install-deps chromium
COPY --from=browsers /ms-playwright /opt/playwright-browsers
RUN chmod -R o+rx /opt/playwright-browsers

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]

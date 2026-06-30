# ── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Inject uv from the official image (no pip needed)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Layer-cache: sync dependencies before copying application code
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project itself
COPY . .
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Bring uv and the full virtualenv from the builder first so that
# `playwright install-deps` can resolve the correct system packages
# for whatever Debian version this base image ships (avoids hardcoding
# package names that change across Debian releases, e.g. libasound2 → libasound2t64).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=builder /build /app

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers

RUN uv run playwright install-deps chromium \
    && uv run playwright install chromium \
    && chmod -R o+rx /opt/playwright-browsers

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]

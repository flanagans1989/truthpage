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

# Playwright Chromium requires these Debian libs at runtime.
# Using playwright install-deps is the canonical way; we also need
# the tool itself available before calling it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Core Chromium runtime
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
        libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libasound2 libpango-1.0-0 libcairo2 \
        libatspi2.0-0 libx11-6 libxcb1 libxext6 \
        # Font rendering (prevents blank-page scrapes)
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Bring uv and the full virtualenv from the builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=builder /build /app

# Download Chromium browser to a world-readable path so the non-root
# appuser can access it at runtime.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN uv run playwright install chromium \
    && chmod -R o+rx /opt/playwright-browsers

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--log-level", "info"]

import os

# Settings reads .env locally; in CI there is none, so provide safe dummies
# BEFORE anything imports app.core.config.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("GEMINI_API_KEY", "test")
os.environ.setdefault("RESEND_API_KEY", "test")

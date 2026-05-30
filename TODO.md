# TrustPages MVP Progress Tracker

## 🟢 HAFTA 1: CORE ENGINE (HEDEF: DETERMINISTIK DIFF & LLM CLASSIFICATION)

- [x] Gün 0: Proje İskeleti, Bağımlılıklar (Uv, FastAPI) ve Canlı /healthz Endpoint'i
- [x] Gün 1: DB Altyapısı (Async Engine, Sessionmaker, DeclarativeBase, Mixins)
- [x] Gün 2: Modeller (Tenant, Subprocessor, ChangeEvent, Subscriber) & İlk Alembic Migration
- [x] Gün 3: Normalizer (selectolax) ve Hasher Motorunun Kurulması
- [x] Gün 4: ChangeDetector (difflib) ve services/monitoring.py Orkestrasyonu
- [x] Gün 5: Bot Koruması: Tier-1 (httpx + proxy) & Tier-2 (Playwright Fallback) Katmanı
- [x] Gün 6: Anthropic Claude Haiku JSON Structured Output ve Sınıflandırma
- [x] Gün 7: APScheduler Cron Sürecinin Bağlanması ve Core Motor Testi

---
## 🔵 HAFTA 2: APPROVAL & API KATMANI

- [x] Gün 8: Approval (Onay) Servisi ve Durum Yönetimi (approve_change_event / reject_change_event)
- [x] Gün 9: Magic Link Auth ve Dashboard İskeleti (JWT, cookie, Jinja2 + Tailwind + HTMX)
- [x] Gün 10: Subprocessor CRUD ve Neon Canlı Bağlantısı (alembic upgrade head, HTMX partial table)
- [x] Gün 11: Onay Kuyruğu Arayüzü (queue.html, diff viewer, HTMX approve/reject partials)
- [x] Gün 12: Public Trust Page ve Subscriber Double Opt-in (/trust/{slug}, subscribe, verify-subscription)
- [x] Gün 13: Notification Servisi ve Resend E-posta Entegrasyonu (mailer.py, auth/public/approval bağlantıları)
- [x] Gün 14: Stripe Entegrasyonu ve Paket Kısıtlamaları (billing.py, webhooks.py, sweep gating doğrulandı)
- [x] Gün 15: Fly.io Deploy, Loglama, Sentry, Lansman Hazırlığı (Dockerfile, fly.toml, logging.config)

---
---
## 🔒 PRE-PRODUCTION AUDIT (31 Mayıs 2026)

- [x] CRITICAL-1: JWT token'lar plaintext log'a yazılıyordu → sadece token prefix loglanıyor
- [x] CRITICAL-2: `.dockerignore` yoktu → `.env` ve sırlar Docker imajına gömülüyordu
- [x] CRITICAL-3: Anthropic API timeout yoktu → 30 saniyelik timeout eklendi
- [x] MEDIUM-1: `/auth/request` rate limiting yoktu → IP + e-posta başına dakikada 3 istek limiti
- [x] MEDIUM-2: Slug çakışması (amazon.com vs amazon.co.uk) → `_get_unique_slug` ile domain suffix / random fallback
- [x] MEDIUM-3: Diff boyutu LLM'e gitmeden kırpılmıyordu → 12.000 karakter limiti
- [x] MEDIUM-4: Connection pool Neon free tier'ı aşıyordu → pool_size=3, max_overflow=1

---
### 📍 EN SON NEREDE KALDIM?

- **Tarih:** 31 Mayıs 2026
- **Mevcut Durum:** MVP + Pre-Production Audit TAMAM. Tüm güvenlik açıkları kapatıldı.
- **Bir Sonraki Adım:** fly deploy komutu ile production'a taşı.

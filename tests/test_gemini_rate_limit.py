"""app/core/llm/rate_limit.py — the shared pacer that stops the free-tier
Gemini quota (requests/minute, account-wide, not per code path) from being
exceeded when several sweep-triggered calls land close together. Hit in
production without this: Sentry TRUSTPAGES-8, 2026-09-02.

Two things matter: the limiter itself actually spaces calls out, and every
Gemini call site in the app (diff classifier, entry extractor, notice
drafter, outreach drafter) actually awaits it before calling the API —
otherwise this is a limiter nothing uses.
"""
import time

import pytest

from app.core.llm.rate_limit import GeminiRateLimiter


class TestGeminiRateLimiter:
    @pytest.mark.asyncio
    async def test_first_call_never_waits(self):
        limiter = GeminiRateLimiter(min_interval_seconds=5.0)
        start = time.monotonic()
        await limiter.wait_turn()
        assert time.monotonic() - start < 0.1

    @pytest.mark.asyncio
    async def test_second_call_waits_out_the_remaining_interval(self):
        limiter = GeminiRateLimiter(min_interval_seconds=0.2)
        await limiter.wait_turn()
        start = time.monotonic()
        await limiter.wait_turn()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.18  # small tolerance for scheduling jitter

    @pytest.mark.asyncio
    async def test_a_call_after_the_interval_has_already_passed_does_not_wait(self):
        limiter = GeminiRateLimiter(min_interval_seconds=0.05)
        await limiter.wait_turn()
        import asyncio

        await asyncio.sleep(0.1)  # let the interval elapse on its own
        start = time.monotonic()
        await limiter.wait_turn()
        assert time.monotonic() - start < 0.03

    @pytest.mark.asyncio
    async def test_calls_are_serialized_never_overlap_the_interval(self):
        # Three concurrent callers must still come out spaced apart, not
        # all released together the moment the first one's wait ends.
        import asyncio

        limiter = GeminiRateLimiter(min_interval_seconds=0.05)
        order: list[float] = []

        async def call():
            await limiter.wait_turn()
            order.append(time.monotonic())

        await asyncio.gather(call(), call(), call())
        order.sort()
        assert order[1] - order[0] >= 0.04
        assert order[2] - order[1] >= 0.04


class TestEveryGeminiCallSiteAwaitsTheSharedLimiter:
    @pytest.mark.asyncio
    async def test_llm_diff_analyzer(self, monkeypatch):
        import app.core.llm.analyzer as analyzer_mod
        from app.core.llm.schemas import DiffAnalysis

        calls = []

        async def spy_wait_turn():
            calls.append("waited")

        monkeypatch.setattr(analyzer_mod.gemini_rate_limiter, "wait_turn", spy_wait_turn)

        instance = analyzer_mod.LLMDiffAnalyzer()
        fake_result = DiffAnalysis(summary="x", classification="COSMETIC", confidence=0.9)
        monkeypatch.setattr(instance, "_call_gemini", lambda raw_diff: fake_result)

        result = await instance.analyze("diff text")
        assert result == fake_result
        assert calls == ["waited"]

    @pytest.mark.asyncio
    async def test_sub_processor_extractor(self, monkeypatch):
        import app.core.llm.extractor as extractor_mod
        from app.core.llm.schemas import SubProcessorList

        calls = []

        async def spy_wait_turn():
            calls.append("waited")

        monkeypatch.setattr(extractor_mod.gemini_rate_limiter, "wait_turn", spy_wait_turn)

        instance = extractor_mod.SubProcessorExtractor()
        fake_result = SubProcessorList(entries=[])
        monkeypatch.setattr(instance, "_call_gemini", lambda page_text: fake_result)

        result = await instance.extract("page text")
        assert result == fake_result
        assert calls == ["waited"]

    @pytest.mark.asyncio
    async def test_article_notice_drafter(self, monkeypatch):
        import app.core.llm.notice as notice_mod
        from app.core.llm.schemas import NoticeDraft

        calls = []

        async def spy_wait_turn():
            calls.append("waited")

        monkeypatch.setattr(notice_mod.gemini_rate_limiter, "wait_turn", spy_wait_turn)

        instance = notice_mod.ArticleNoticeDrafter()
        fake_result = NoticeDraft(subject="s", body="b")
        monkeypatch.setattr(instance, "_call_gemini", lambda **kwargs: fake_result)

        result = await instance.draft(
            company="Acme", vendor="Stripe", vendor_url="https://stripe.com",
            detected_on="01 Sep", summary="x", raw_diff="+ x",
        )
        assert result == fake_result
        assert calls == ["waited"]

    @pytest.mark.asyncio
    async def test_outreach_drafter(self, monkeypatch):
        import app.core.llm.outreach as outreach_mod
        from app.core.llm.schemas import OutreachDraft

        calls = []

        async def spy_wait_turn():
            calls.append("waited")

        monkeypatch.setattr(outreach_mod.gemini_rate_limiter, "wait_turn", spy_wait_turn)

        instance = outreach_mod.OutreachDrafter()
        fake_result = OutreachDraft(templates=[])
        monkeypatch.setattr(instance, "_call_gemini", lambda **kwargs: fake_result)

        result = await instance.draft(company="Acme", founder="Jane", vendor1="Stripe", vendor2="AWS")
        assert result == fake_result
        assert calls == ["waited"]

"""Cold-outreach drafting for the admin-only Outreach Generator.

Same shape as ArticleNoticeDrafter: a sync Gemini client called through
asyncio.to_thread, run once per request from a human waiting on it, so it
can fail loudly rather than return filler. Unlike the notice drafter this
output is never sent automatically — it is text for the admin to read,
edit and paste into LinkedIn or an email client themselves.
"""
import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.llm.schemas import OutreachDraft

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

_SYSTEM_PROMPT = """\
You draft cold outreach for TrustPages, a sub-processor compliance monitoring SaaS, writing to \
a specific target company's founder.

TrustPages watches a company's vendors' (sub-processor) privacy policy pages, classifies \
detected changes as material or cosmetic with Gemini 2.5 Flash, and gives an approval queue plus \
a downloadable, SHA-256-verified audit evidence pack (raw HTML, hash, timestamp, diff) — proof a \
GDPR Article 28(2) sub-processor notice obligation is actually being met, not just claimed. Free \
plan: 3 vendors, no card. Paid: $29/month (10 vendors) or $89/month (30 vendors, full audit pack).

You are given the target company's name, its founder's name, and two vendors (sub-processors) \
we already know they use. Use that as proof of research, not as a threat — the message should \
read as "we looked at your stack," never as "we are watching you."

Produce exactly three templates, each a distinct angle (vary these — direct compliance gap, \
curiosity/personalized opener, social proof or peer comparison — do not use the same opening \
line twice), and each written twice: once in English, once in German, as equivalent messages in \
each market's own register, not a literal translation of each other.

Rules:
- Address the founder by name. Name the target company. Name the two vendors naturally, once \
each, as evidence you looked — never both in the same sentence like a mail-merge field.
- No em dashes, no "I hope this finds you well", no exclamation points, no emoji.
- LinkedIn templates: under 80 words, no subject line, one clear call to action, casual but \
professional register — this is a DM, not a memo.
- Email templates: a real subject line, 100-160 words, one call to action, slightly more formal \
than the LinkedIn register but still first-person and specific to this company.
- Never invent a fact about the target company beyond what you were given. Never claim we are \
already monitoring them — we are not, that is the offer.
- Never fabricate a statistic, customer count, or testimonial.\
"""


def build_prompt(*, company: str, founder: str, vendor1: str, vendor2: str) -> str:
    return "\n".join(
        [
            f"Target company: {company}",
            f"Founder: {founder}",
            f"Known vendor 1: {vendor1}",
            f"Known vendor 2: {vendor2}",
        ]
    )


class OutreachDrafter:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _call_gemini(self, *, company: str, founder: str, vendor1: str, vendor2: str) -> OutreachDraft:
        prompt = build_prompt(company=company, founder=founder, vendor1=vendor1, vendor2=vendor2)
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=OutreachDraft,
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty outreach draft")
        draft = OutreachDraft.model_validate(json.loads(response.text))
        logger.info("Outreach drafted for '%s' (%d templates)", company, len(draft.templates))
        return draft

    async def draft(self, *, company: str, founder: str, vendor1: str, vendor2: str) -> OutreachDraft:
        return await asyncio.wait_for(
            asyncio.to_thread(
                self._call_gemini, company=company, founder=founder, vendor1=vendor1, vendor2=vendor2
            ),
            timeout=45.0,
        )

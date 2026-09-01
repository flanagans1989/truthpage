"""Drafting of the Article 28(2) notice a tenant owes its own customers.

Kept apart from the diff analyzer on purpose: classification runs on every
detected change and has to stay cheap, while this runs once, on request, for
a change a human has already decided matters — so it can spend more, and it
must fail loudly rather than return filler. The tenant is about to send this
text to their customers.
"""
import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.llm.schemas import NoticeDraft

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

_SYSTEM_PROMPT = """\
You draft GDPR Article 28(2) sub-processor change notifications for a B2B SaaS company \
writing to its own customers.

Context: the company uses vendors (sub-processors). One of those vendors has changed its \
own sub-processor list. Under a general written authorisation the company must inform its \
customers of the intended addition or replacement and give them a genuine opportunity to \
object, typically within 10-30 days depending on the DPA.

Rules:
- Write as the company, addressing its customers. Never mention any monitoring tool.
- State plainly what changed and which vendor changed it. Do not exaggerate the change.
- Use the detection date exactly as supplied. Never invent dates, numbers, or \
sub-processor names that are not in the material you are given.
- Include one sentence telling the customer how to object, using the placeholder \
[OBJECTION WINDOW] for the number of days and [CONTACT] for the address to write to. \
Those two are the only placeholders permitted.
- Plain text, no markdown, no bullet characters. Six to twelve sentences.
- Put the greeting on its own line and separate paragraphs with a blank line. The text is \
pasted straight into an email; a wall of prose with the greeting run into the first \
sentence is the giveaway that nobody read it.
- If the change carries no Article 28 consequence, say so in one short paragraph rather \
than inventing an obligation.\
"""


def build_prompt(
    *,
    company: str,
    vendor: str,
    vendor_url: str,
    detected_on: str,
    summary: str,
    raw_diff: str,
) -> str:
    """Assembles the material the model may draw on — and nothing else.

    Module-level so its contents can be asserted: every fact in the notice has
    to come from one of these lines, and a field silently dropped here would
    become a notice that omits the vendor or the date.
    """
    return "\n".join(
        [
            f"Company writing the notice: {company}",
            f"Vendor whose sub-processor list changed: {vendor}",
            f"Vendor page monitored: {vendor_url}",
            f"Date the change was detected: {detected_on}",
            f"Summary of the change: {summary}",
            "",
            "Diff of the vendor page:",
            "```diff",
            raw_diff,
            "```",
        ]
    )


class ArticleNoticeDrafter:
    def __init__(self) -> None:
        # Sync client called through asyncio.to_thread, as in LLMDiffAnalyzer.
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _call_gemini(
        self,
        *,
        company: str,
        vendor: str,
        vendor_url: str,
        detected_on: str,
        summary: str,
        raw_diff: str,
    ) -> NoticeDraft:
        prompt = build_prompt(
            company=company,
            vendor=vendor,
            vendor_url=vendor_url,
            detected_on=detected_on,
            summary=summary,
            raw_diff=raw_diff,
        )
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=NoticeDraft,
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty notice draft")
        draft = NoticeDraft.model_validate(json.loads(response.text))
        logger.info("Notice drafted for vendor '%s' (%d chars)", vendor, len(draft.body))
        return draft

    async def draft(
        self,
        *,
        company: str,
        vendor: str,
        vendor_url: str,
        detected_on: str,
        summary: str,
        raw_diff: str,
    ) -> NoticeDraft:
        """Returns a draft or raises. Callers surface the failure to the tenant."""
        return await asyncio.wait_for(
            asyncio.to_thread(
                self._call_gemini,
                company=company,
                vendor=vendor,
                vendor_url=vendor_url,
                detected_on=detected_on,
                summary=summary,
                raw_diff=raw_diff,
            ),
            timeout=45.0,
        )

"""Turning a sub-processor page into a list.

Monitoring only ever needed the page as text: hash it, diff it, ask whether
the diff matters. A public directory needs the other thing — the actual
entries, so a reader (and a search engine) sees "Stripe uses these fourteen
sub-processors" rather than a wall of scraped prose.

Runs once per detected change, not per page view: these pages move about
once a month, so the cost is a rounding error, and a stored list renders
instantly.
"""
import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.llm.rate_limit import gemini_rate_limiter
from app.core.llm.schemas import SubProcessorList

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

# Pages run to tens of thousands of characters (Google Cloud's is ~62k).
# Flash takes it, but the cap keeps a pathological page from becoming a
# pathological bill.
_MAX_CHARS = 40_000

_SYSTEM_PROMPT = """\
You extract the sub-processor table from a vendor's public sub-processor page.

Return one entry per sub-processor the vendor lists. Rules:
- Copy names exactly as written on the page. Do not normalise, expand or \
correct them, and never add an entry that is not on the page.
- `purpose` is what the page says the sub-processor is used for, in a few \
words. `location` is the country or region the page gives. Leave either \
empty when the page does not say — an empty field is correct, an invented \
one is not.
- Ignore navigation, headers, legal boilerplate and contact details. Only \
the listed sub-processors.
- If the text contains no sub-processor list at all, return an empty list \
rather than guessing.\
"""


class SubProcessorExtractor:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _call_gemini(self, page_text: str) -> SubProcessorList:
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=f"Sub-processor page text:\n\n{page_text[:_MAX_CHARS]}",
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=SubProcessorList,
                # Transcription, not reasoning.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        if not response.text:
            raise RuntimeError("Gemini returned an empty extraction")
        return SubProcessorList.model_validate(json.loads(response.text))

    async def extract(self, page_text: str) -> SubProcessorList:
        await gemini_rate_limiter.wait_turn()
        return await asyncio.wait_for(
            asyncio.to_thread(self._call_gemini, page_text), timeout=60.0
        )


def diff_entries(
    old: list[dict] | None, new: list[dict] | None
) -> tuple[list[str], list[str]]:
    """Names added and removed between two extractions.

    Compared case-insensitively on the name alone: a vendor that rewords a
    purpose column has not added a sub-processor, and reporting it as one
    would make the directory cry wolf.
    """
    def names(rows: list[dict] | None) -> dict[str, str]:
        return {
            (row.get("name") or "").strip().lower(): (row.get("name") or "").strip()
            for row in (rows or [])
            if (row.get("name") or "").strip()
        }

    before, after = names(old), names(new)
    added = [after[k] for k in after.keys() - before.keys()]
    removed = [before[k] for k in before.keys() - after.keys()]
    return sorted(added), sorted(removed)

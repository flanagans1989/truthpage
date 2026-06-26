import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.core.llm.schemas import DiffAnalysis

logger = logging.getLogger(__name__)

_MODEL = "gemini-2.5-flash"

_SYSTEM_PROMPT = """\
You are a sub-processor compliance assistant for a privacy policy monitoring platform.

Your task is to analyze diffs of privacy policy pages and determine whether changes are legally \
material or merely cosmetic. You must respond with a valid JSON object matching the schema exactly.

Definitions:
- MATERIAL: Any change that affects data subjects' rights or risks — adding/removing a \
sub-processor, changing data retention periods, introducing new data categories, changing \
processing purposes or legal basis, updating data transfer mechanisms.
- COSMETIC: Purely stylistic changes — fixing typos, rewording without meaning change, \
reformatting, updating contact details without policy change.
- UNCERTAIN: Use this when the diff is ambiguous, truncated, or you cannot confidently \
determine materiality.

Be concise and precise. Your summary should name the specific change, not just describe \
that a change occurred.\
"""

_FALLBACK = DiffAnalysis(
    summary="LLM analysis failed — manual review required.",
    classification="UNCERTAIN",
    confidence=0.0,
)


class LLMDiffAnalyzer:
    def __init__(self) -> None:
        # Sync client — called via asyncio.to_thread to avoid blocking the event loop.
        # Avoids the NotImplementedError raised by google-genai's .aio interface.
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def _call_gemini(self, raw_diff: str) -> DiffAnalysis:
        """Synchronous Gemini call — runs in a thread pool via asyncio.to_thread."""
        prompt = (
            "Analyze the following privacy policy diff:\n\n"
            f"```diff\n{raw_diff}\n```"
        )
        response = self._client.models.generate_content(
            model=_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=DiffAnalysis,
            ),
        )
        if not response.text:
            logger.error("Gemini returned empty response")
            return _FALLBACK
        result = DiffAnalysis.model_validate(json.loads(response.text))
        logger.info(
            "Gemini analysis: %s (confidence=%.2f)", result.classification, result.confidence
        )
        return result

    async def analyze(self, raw_diff: str) -> DiffAnalysis:
        """
        Sends the diff to Gemini Flash. Runs the sync SDK call in a thread pool
        with a 30-second timeout so the sweep loop is never blocked.
        """
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._call_gemini, raw_diff),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.error("Gemini API timed out after 30 s; defaulting to UNCERTAIN")
            return _FALLBACK
        except Exception:
            logger.exception("Gemini analysis failed; defaulting to UNCERTAIN")
            return _FALLBACK

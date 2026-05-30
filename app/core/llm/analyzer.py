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
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def analyze(self, raw_diff: str) -> DiffAnalysis:
        """
        Sends the diff to Gemini Flash and returns a structured DiffAnalysis via
        JSON mode with a Pydantic response schema. Times out after 30 s; any
        failure falls back to UNCERTAIN so the sweep loop is never blocked.
        """
        prompt = (
            "Analyze the following privacy policy diff:\n\n"
            f"```diff\n{raw_diff}\n```"
        )
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=_MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=DiffAnalysis,
                    ),
                ),
                timeout=30.0,
            )
            if not response.text:
                logger.error("Gemini returned empty response; defaulting to UNCERTAIN")
                return _FALLBACK

            result = DiffAnalysis.model_validate(json.loads(response.text))
            logger.debug(
                "Gemini analysis: %s (confidence=%.2f)", result.classification, result.confidence
            )
            return result

        except asyncio.TimeoutError:
            logger.error("Gemini API timed out after 30 s; defaulting to UNCERTAIN")
            return _FALLBACK
        except Exception:
            logger.exception("Gemini analysis failed; defaulting to UNCERTAIN")
            return _FALLBACK

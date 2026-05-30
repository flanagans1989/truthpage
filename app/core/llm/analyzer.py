import logging

import anthropic

from app.core.config import settings
from app.core.llm.schemas import DiffAnalysis

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """\
You are a sub-processor compliance assistant for a privacy policy monitoring platform.

Your task is to analyze diffs of privacy policy pages and determine whether changes are legally \
material or merely cosmetic. You must call the `analyze_diff` tool with your structured analysis.

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

_TOOL_SCHEMA: list[anthropic.types.ToolParam] = [
    {
        "name": "analyze_diff",
        "description": "Return a structured analysis of a privacy policy diff.",
        "input_schema": DiffAnalysis.model_json_schema(),
    }
]


class LLMDiffAnalyzer:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=30.0,  # prevent a slow/hung API call from blocking the sweep loop
        )

    async def analyze(self, raw_diff: str) -> DiffAnalysis:
        """
        Sends the diff to Claude Haiku and forces a structured DiffAnalysis response
        via tool_use, guaranteeing valid JSON that matches the Pydantic schema.
        """
        response = await self._client.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=_TOOL_SCHEMA,
            tool_choice={"type": "tool", "name": "analyze_diff"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Analyze the following privacy policy diff and call `analyze_diff`:\n\n"
                        f"```diff\n{raw_diff}\n```"
                    ),
                }
            ],
        )

        tool_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if tool_block is None:
            logger.error("Claude returned no tool_use block; defaulting to UNCERTAIN")
            return DiffAnalysis(
                summary="Analysis unavailable — model returned no structured output.",
                classification="UNCERTAIN",
                confidence=0.0,
            )

        return DiffAnalysis.model_validate(tool_block.input)

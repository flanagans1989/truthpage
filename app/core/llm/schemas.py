from typing import Literal

from pydantic import BaseModel, Field


class DiffAnalysis(BaseModel):
    summary: str = Field(
        description=(
            "A concise, human-readable summary of the change in plain language. "
            "Supports both Turkish and English. Be specific: name what changed, not just that something changed."
        )
    )
    classification: Literal["MATERIAL", "COSMETIC", "UNCERTAIN"] = Field(
        description=(
            "MATERIAL: Critical changes — new sub-processor added/removed, "
            "location or purpose change, data retention change, new data category. "
            "COSMETIC: Trivial changes — typo fixes, rephrasing without meaning change, formatting. "
            "UNCERTAIN: Cannot confidently determine materiality."
        )
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification, between 0.0 and 1.0.",
    )

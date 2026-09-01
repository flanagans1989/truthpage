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


class NoticeDraft(BaseModel):
    """A drafted Article 28(2) notification to the tenant's own customers."""

    subject: str = Field(
        description="Email subject line. Names the vendor and that a sub-processor change occurred."
    )
    body: str = Field(
        description=(
            "The notice body in plain text, ready to paste into an email. States what changed, "
            "which vendor, the date it was detected, and that the customer may object within the "
            "window their DPA provides. No markdown, no placeholders other than the ones listed "
            "in the instructions."
        )
    )

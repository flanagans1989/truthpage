import pytest
from pydantic import ValidationError

from app.core.llm.notice import _SYSTEM_PROMPT, build_prompt
from app.core.llm.schemas import NoticeDraft

FIELDS = dict(
    company="Acme Inc",
    vendor="Stripe",
    vendor_url="https://stripe.com/legal/subprocessors",
    detected_on="01 September 2026",
    summary="Added Anthropic PBC as a sub-processor for support tooling.",
    raw_diff="+ Anthropic PBC — support tooling — United States",
)


class TestBuildPrompt:
    def test_every_supplied_fact_reaches_the_prompt(self):
        prompt = build_prompt(**FIELDS)
        for value in FIELDS.values():
            assert value in prompt

    def test_diff_is_fenced_so_it_cannot_read_as_instructions(self):
        prompt = build_prompt(**FIELDS)
        assert "```diff" in prompt
        assert prompt.rstrip().endswith("```")

    def test_diff_is_the_last_section(self):
        # Anything after the diff would sit outside the fence and read as
        # instruction text rather than as monitored content.
        prompt = build_prompt(**FIELDS)
        assert prompt.index("Diff of the vendor page:") > prompt.index("Summary of the change:")


class TestSystemPrompt:
    def test_names_the_two_permitted_placeholders(self):
        assert "[OBJECTION WINDOW]" in _SYSTEM_PROMPT
        assert "[CONTACT]" in _SYSTEM_PROMPT

    def test_forbids_invented_facts(self):
        assert "Never invent" in _SYSTEM_PROMPT


class TestNoticeDraftSchema:
    def test_accepts_a_complete_draft(self):
        draft = NoticeDraft(subject="Sub-processor change at Stripe", body="Dear customer, ...")
        assert draft.subject and draft.body

    def test_rejects_a_draft_missing_the_body(self):
        with pytest.raises(ValidationError):
            NoticeDraft(subject="Sub-processor change at Stripe")

"""The /compare rules, checked against the source the page actually reads.

The category copy lives in the locale files now, so these read from there.
The nameless rule is the reason this file exists: it has to hold in four
languages, and a translator adding "unlike SafeBase" for clarity is exactly
the failure it catches.
"""
import json
from pathlib import Path

import pytest

from app.core.comparisons import LEGACY_SLUGS, OURS, VERIFIED_ON
from app.core.i18n import SUPPORTED_LANGS

LOCALES = Path(__file__).parent.parent / "locales"

# The page describes shapes of product, not companies. These are the names it
# must never carry — the whole point of the rewrite.
FORBIDDEN_NAMES = (
    "registora", "dpaflow", "dpa flow", "pagecrawl", "page crawl", "orbiq",
    "relyance", "vanta", "drata", "safebase", "onetrust", "apify", "conveyor",
    "secureframe", "trustcloud",
)


def _catalog(lang: str) -> dict:
    return json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8"))


def _compare_text(lang: str) -> str:
    """Every string the /compare page renders, in one blob."""
    catalog = _catalog(lang)
    parts: list[str] = [VERIFIED_ON, *OURS.values(), *catalog["compare.gaps"]]
    for c in catalog["compare.categories"]:
        parts += [c["slug"], c["name"], c["shape"], c["price"], c["pick_them_when"]]
        parts += c["strengths"] + c["limits"]
    for entry in catalog["compare.position"]:
        parts += [entry["title"], entry["body"]]
    parts += [catalog[k] for k in catalog if k.startswith("compare.") and isinstance(catalog[k], str)]
    return " ".join(parts).lower()


class TestNoCompetitorNames:
    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_page_text_names_no_competitor(self, lang):
        # Whole tokens: French "davantage" contains "vanta" and is innocent.
        words = set(
            _compare_text(lang)
            .replace(",", " ").replace(".", " ").replace(chr(34), " ")
            .replace("(", " ").replace(")", " ").replace(";", " ")
            .split()
        )
        found = [name for name in FORBIDDEN_NAMES if name in words]
        assert not found, f"competitor named on /compare ({lang}): {found}"

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_legacy_slugs_are_redirect_targets_not_content(self, lang):
        slugs = {c["slug"] for c in _catalog(lang)["compare.categories"]}
        assert set(LEGACY_SLUGS).isdisjoint(slugs)


class TestCategoryContent:
    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_every_category_is_complete(self, lang):
        for c in _catalog(lang)["compare.categories"]:
            assert c["slug"] and c["name"] and c["shape"] and c["price"], c["slug"]
            assert c["strengths"] and c["limits"] and c["pick_them_when"], c["slug"]

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_slugs_are_unique_and_stable_across_languages(self, lang):
        slugs = [c["slug"] for c in _catalog(lang)["compare.categories"]]
        # Also the anchor targets (#privacy-suites), so they must not be
        # translated along with the heading above them.
        assert len(slugs) == len(set(slugs))
        assert slugs == [c["slug"] for c in _catalog("en")["compare.categories"]]

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_each_category_says_when_to_choose_it_over_us(self, lang):
        # A comparison page that never concedes a case is not a comparison.
        for c in _catalog(lang)["compare.categories"]:
            assert len(c["pick_them_when"]) > 40, (lang, c["slug"])

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_we_publish_our_own_gaps(self, lang):
        assert len(_catalog(lang)["compare.gaps"]) >= 3

    @pytest.mark.parametrize("lang", SUPPORTED_LANGS)
    def test_position_entries_have_a_title_and_a_body(self, lang):
        for entry in _catalog(lang)["compare.position"]:
            assert entry["title"].strip() and entry["body"].strip()

    def test_pricing_and_verification_date_are_stated(self):
        assert OURS["free"] and OURS["paid"]
        assert VERIFIED_ON.strip()

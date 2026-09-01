from app.core.comparisons import (
    CATEGORIES,
    LEGACY_SLUGS,
    OUR_GAPS,
    OUR_POSITION,
    OURS,
    VERIFIED_ON,
)

# The page exists to describe shapes of product, not to name anyone. These are
# the names it must never carry — the whole point of the rewrite.
FORBIDDEN_NAMES = (
    "registora",
    "dpaflow",
    "dpa flow",
    "pagecrawl",
    "page crawl",
    "orbiq",
    "relyance",
    "vanta",
    "drata",
    "safebase",
    "onetrust",
    "apify",
    "conveyor",
    "secureframe",
    "trustcloud",
)


def _all_page_text() -> str:
    parts: list[str] = [VERIFIED_ON, *OURS.values(), *OUR_GAPS]
    for c in CATEGORIES:
        parts += [c.slug, c.name, c.shape, c.price, c.pick_them_when, *c.strengths, *c.limits]
    for title, body in OUR_POSITION:
        parts += [title, body]
    return " ".join(parts).lower()


class TestNoCompetitorNames:
    def test_page_text_names_no_competitor(self):
        text = _all_page_text()
        found = [name for name in FORBIDDEN_NAMES if name in text]
        assert not found, f"competitor named on /compare: {found}"

    def test_legacy_slugs_are_not_reachable_content(self):
        # They survive only as redirect targets, never as rendered copy.
        assert set(LEGACY_SLUGS).isdisjoint({c.slug for c in CATEGORIES})


class TestCategoryContent:
    def test_every_category_is_complete(self):
        for c in CATEGORIES:
            assert c.slug and c.name and c.shape and c.price, c.slug
            assert c.strengths, c.slug
            assert c.limits, c.slug
            assert c.pick_them_when, c.slug

    def test_slugs_are_unique(self):
        slugs = [c.slug for c in CATEGORIES]
        assert len(slugs) == len(set(slugs))

    def test_each_category_says_when_to_choose_it_over_us(self):
        # A comparison page that never concedes a case is not a comparison.
        for c in CATEGORIES:
            assert len(c.pick_them_when) > 40, c.slug

    def test_we_publish_our_own_gaps(self):
        assert len(OUR_GAPS) >= 3

    def test_our_position_entries_are_pairs_with_content(self):
        for entry in OUR_POSITION:
            title, body = entry
            assert title.strip() and body.strip()

    def test_pricing_and_verification_date_are_stated(self):
        assert OURS["free"] and OURS["paid"]
        assert VERIFIED_ON.strip()

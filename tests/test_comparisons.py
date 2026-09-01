from app.core.comparisons import COMPARISONS, OURS, VERIFIED_ON


class TestComparisonContent:
    def test_slug_matches_its_key(self):
        # The key is what /vs/{slug} looks up; the slug is what the "also
        # compared" links point at. A mismatch is a 404 from our own footer.
        for key, entry in COMPARISONS.items():
            assert key == entry.slug

    def test_every_page_has_a_table_and_both_verdict_columns(self):
        for entry in COMPARISONS.values():
            assert entry.rows, entry.slug
            assert entry.they_win, entry.slug
            assert entry.we_win, entry.slug

    def test_each_row_has_three_cells(self):
        for entry in COMPARISONS.values():
            for row in entry.rows:
                assert len(row) == 3, (entry.slug, row)

    def test_no_row_cell_is_blank(self):
        for entry in COMPARISONS.values():
            for row in entry.rows:
                assert all(cell.strip() for cell in row), (entry.slug, row)

    def test_competitor_link_is_absolute(self):
        for entry in COMPARISONS.values():
            assert entry.url.startswith("https://"), entry.slug

    def test_pricing_is_stated_for_both_sides(self):
        assert OURS["free"] and OURS["paid"]
        for entry in COMPARISONS.values():
            assert entry.pricing.strip(), entry.slug

    def test_verification_date_is_present(self):
        # Shown on every page; the figures are only defensible with a date on them.
        assert VERIFIED_ON.strip()

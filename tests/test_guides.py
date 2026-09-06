"""Content-marketing pages, not product pages — same "English only, no
hreflang alternates" shape as the legal pages (see
ENGLISH_ONLY_GUIDE_PATHS in app/routers/pages.py) since both quote
regulatory text and reference our own English DPA."""


class TestArticle28Guide:
    def test_page_loads_and_quotes_the_article(self, anon_client):
        response = anon_client.get("/guides/article-28-notice-template")
        assert response.status_code == 200
        body = response.text
        assert "Article 28(2)" in body
        assert "prior written authorization" in body or "opportunity to object" in body

    def test_it_is_honest_that_the_notice_period_comes_from_the_dpa_not_the_article(self, anon_client):
        body = anon_client.get("/guides/article-28-notice-template").text
        assert "doesn't set a notice period" in body

    def test_it_links_to_the_other_guide_and_to_pricing(self, anon_client):
        body = anon_client.get("/guides/article-28-notice-template").text
        assert "/guides/dora-ict-register" in body
        assert '/pricing"' in body


class TestDoraGuide:
    def test_page_loads_and_names_the_register(self, anon_client):
        response = anon_client.get("/guides/dora-ict-register")
        assert response.status_code == 200
        assert "register of information" in response.text

    def test_it_does_not_claim_to_file_the_register_for_you(self, anon_client):
        """The product watches sub-processor pages; it does not submit
        anything to a supervisor. Overstating that is the kind of claim
        test_claim_accuracy.py exists to catch."""
        body = anon_client.get("/guides/dora-ict-register").text
        assert "doesn't file your register for you" in body

    def test_it_links_to_the_other_guide_and_to_pricing(self, anon_client):
        body = anon_client.get("/guides/dora-ict-register").text
        assert "/guides/article-28-notice-template" in body
        assert '/pricing"' in body


class TestGuidesAreInTheSitemap:
    def test_both_guides_are_listed_without_hreflang_alternates(self, anon_client):
        from app.routers.pages import ENGLISH_ONLY_GUIDE_PATHS

        xml = anon_client.get("/sitemap.xml").text
        for path in ENGLISH_ONLY_GUIDE_PATHS:
            assert f"<url><loc>https://" in xml
            assert f"{path}</loc></url>" in xml

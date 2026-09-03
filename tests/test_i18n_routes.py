"""The routing half of i18n: prefixes, redirects, hreflang, sitemap.

Run against the throwaway SQLite database from conftest, never the .env one.
"""
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.db.models.vendor import Vendor


@pytest_asyncio.fixture
async def stripe(session_factory):
    async with session_factory() as session:
        vendor = Vendor(
            slug="stripe",
            name="Stripe",
            monitored_url="https://stripe.com/legal/service-providers",
            homepage_url="https://stripe.com",
            is_published=True,
            entries=[{"name": "AWS", "purpose": "hosting", "location": "US"}],
            entries_updated_at=datetime(2026, 9, 1, tzinfo=UTC),
        )
        session.add(vendor)
        await session.commit()
    return vendor


class TestPrefixedPages:
    @pytest.mark.parametrize("path", ["/", "/pricing", "/compare"])
    @pytest.mark.parametrize("lang", ["de", "fr", "es"])
    def test_every_static_page_exists_in_every_language(self, anon_client, lang, path):
        url = f"/{lang}" if path == "/" else f"/{lang}{path}"
        response = anon_client.get(url)
        assert response.status_code == 200
        assert f'<html lang="{lang}"' in response.text

    def test_the_german_landing_page_is_actually_german(self, anon_client):
        text = anon_client.get("/de").text
        assert "Unterauftragsverarbeiter" in text
        assert "DSGVO" in text
        # …and not a half-translated page with English headings left in it.
        assert "Answer security reviews" not in text

    def test_the_french_page_uses_the_local_regulatory_terms(self, anon_client):
        text = anon_client.get("/fr/pricing").text
        assert "sous-traitants ultérieurs" in text
        assert "RGPD" in text

    def test_an_unsupported_language_is_a_404_not_a_redirect(self, anon_client):
        # A redirect would invent an infinite URL space for crawlers.
        assert anon_client.get("/kk", follow_redirects=False).status_code == 404
        assert anon_client.get("/kk/pricing", follow_redirects=False).status_code == 404

    def test_english_prefix_redirects_to_the_root(self, anon_client):
        # Two URLs with identical text is the duplicate-content problem the
        # whole prefix scheme exists to avoid.
        r = anon_client.get("/en/pricing", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, "/pricing")
        r = anon_client.get("/en", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, "/")

    def test_legal_pages_stay_english_and_redirect_from_a_prefix(self, anon_client):
        for path in ("terms", "privacy", "refunds"):
            r = anon_client.get(f"/de/{path}", follow_redirects=False)
            assert (r.status_code, r.headers["location"]) == (301, f"/{path}")

    def test_the_language_router_does_not_shadow_real_routes(self, anon_client):
        # /{lang} matches any single segment, so this is the regression that
        # would take the health check — and Render's deploys — down.
        # Not 200: /healthz opens its own session against the (dummy) engine
        # rather than the injected one, so it fails here. 404 is the symptom
        # that matters — it would mean /{lang} answered instead.
        assert anon_client.get("/healthz").status_code != 404
        assert anon_client.get("/robots.txt").status_code == 200
        assert anon_client.get("/vendors").status_code == 200


class TestLanguageNudge:
    def test_a_german_browser_is_offered_the_german_root(self, anon_client):
        r = anon_client.get(
            "/", headers={"accept-language": "de-DE,de;q=0.9,en;q=0.8"}, follow_redirects=False
        )
        assert (r.status_code, r.headers["location"]) == (302, "/de")

    def test_a_crawler_is_never_redirected(self, anon_client):
        r = anon_client.get(
            "/",
            headers={
                "accept-language": "de-DE,de;q=0.9",
                "user-agent": "Mozilla/5.0 (compatible; Googlebot/2.1)",
            },
            follow_redirects=False,
        )
        assert r.status_code == 200

    def test_an_english_speaker_is_left_alone(self, anon_client):
        r = anon_client.get(
            "/", headers={"accept-language": "en-GB,en;q=0.9"}, follow_redirects=False
        )
        assert r.status_code == 200

    def test_a_remembered_choice_beats_the_browser_header(self, anon_client):
        anon_client.cookies.set("lang", "en")
        r = anon_client.get(
            "/", headers={"accept-language": "de-DE,de;q=0.9"}, follow_redirects=False
        )
        assert r.status_code == 200

    def test_visiting_a_localized_page_is_remembered(self, anon_client):
        r = anon_client.get("/fr", follow_redirects=False)
        assert r.cookies.get("lang") == "fr"

    def test_a_deep_link_is_never_redirected_by_language(self, anon_client):
        r = anon_client.get(
            "/pricing", headers={"accept-language": "de-DE,de;q=0.9"}, follow_redirects=False
        )
        assert r.status_code == 200


class TestHreflang:
    def _links(self, html: str) -> dict[str, str]:
        import re

        return {
            m.group(1): m.group(2)
            for m in re.finditer(
                r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', html
            )
        }

    def test_every_page_declares_the_whole_set(self, anon_client):
        links = self._links(anon_client.get("/de/pricing").text)
        assert set(links) == {"en", "de", "fr", "es", "x-default"}
        assert links["en"].endswith("/pricing")
        assert links["de"].endswith("/de/pricing")
        assert links["x-default"] == links["en"]

    def test_the_set_is_identical_whichever_language_you_arrive_in(self, anon_client):
        # Non-reciprocal hreflang is ignored wholesale by search engines.
        assert self._links(anon_client.get("/").text) == self._links(
            anon_client.get("/es").text
        )

    def test_canonical_points_at_the_page_itself_not_at_english(self, anon_client):
        html = anon_client.get("/fr/compare").text
        assert '<link rel="canonical"' in html
        canonical = html.split('<link rel="canonical" href="')[1].split('"')[0]
        assert canonical.endswith("/fr/compare")

    def test_vendor_pages_carry_them_too(self, anon_client, stripe):
        links = self._links(anon_client.get("/de/vendors/stripe-subprocessors").text)
        assert links["fr"].endswith("/fr/vendors/stripe-subprocessors")


class TestVendorPages:
    def test_the_keyword_url_is_the_canonical_one(self, anon_client, stripe):
        assert anon_client.get("/vendors/stripe-subprocessors").status_code == 200

    def test_the_old_bare_slug_redirects_permanently(self, anon_client, stripe):
        r = anon_client.get("/vendors/stripe", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, "/vendors/stripe-subprocessors")

    def test_the_redirect_keeps_the_language(self, anon_client, stripe):
        r = anon_client.get("/fr/vendors/stripe", follow_redirects=False)
        assert r.headers["location"] == "/fr/vendors/stripe-subprocessors"

    def test_an_unpublished_vendor_is_still_a_404_in_every_language(self, anon_client):
        assert anon_client.get("/de/vendors/nobody-subprocessors").status_code == 404

    def test_the_page_is_translated_but_the_data_is_not(self, anon_client, stripe):
        html = anon_client.get("/de/vendors/stripe-subprocessors").text
        assert "Unterauftragsverarbeiter von Stripe" in html
        # The vendor's own list is their text, not ours to translate.
        assert "AWS" in html

    def test_structured_data_describes_the_page_it_sits_on(self, anon_client, stripe):
        import json

        html = anon_client.get("/fr/vendors/stripe-subprocessors").text
        blob = html.split('<script type="application/ld+json">')[1].split("</script>")[0]
        data = json.loads(blob)
        assert data["@type"] == "Dataset"
        assert data["inLanguage"] == "fr"
        assert data["url"].endswith("/fr/vendors/stripe-subprocessors")
        assert "Sous-traitants ultérieurs" in data["name"]

    def test_the_index_links_to_the_canonical_urls(self, anon_client, stripe):
        html = anon_client.get("/es/vendors").text
        assert "/es/vendors/stripe-subprocessors" in html


class TestSitemap:
    def test_every_page_is_listed_in_every_language(self, anon_client, stripe):
        xml = anon_client.get("/sitemap.xml").text
        for lang_path in ("/pricing", "/de/pricing", "/fr/pricing", "/es/pricing"):
            assert f"<loc>https://" in xml
            assert lang_path + "</loc>" in xml

    def test_vendor_pages_use_the_canonical_slug_and_carry_lastmod(self, anon_client, stripe):
        xml = anon_client.get("/sitemap.xml").text
        assert "/de/vendors/stripe-subprocessors</loc>" in xml
        assert "<lastmod>2026-09-01</lastmod>" in xml

    def test_each_entry_carries_its_alternates(self, anon_client, stripe):
        xml = anon_client.get("/sitemap.xml").text
        assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in xml
        assert '<xhtml:link rel="alternate" hreflang="x-default"' in xml
        # Four languages plus x-default, on each of the four language URLs.
        from app.routers.pages import ENGLISH_ONLY_LEGAL_PATHS

        assert xml.count('hreflang="de"') == xml.count("<url>") - len(
            ENGLISH_ONLY_LEGAL_PATHS
        )  # legal pages carry none

    def test_the_english_only_legal_pages_are_listed_without_alternates(self, anon_client):
        xml = anon_client.get("/sitemap.xml").text
        assert "<url><loc>https://" in xml
        assert "/terms</loc></url>" in xml

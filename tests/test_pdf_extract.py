"""Slack, Heroku and Salesforce's sub-processor "pages" are all one static
PDF (see app/core/vendor_seeds.py's 2026-09-06 note) — this is the module
that makes such a source readable at all."""
from app.core.scraper.normalizer import HTMLNormalizer
from app.core.scraper.pdf_extract import extract_pdf_text, is_pdf_response, pdf_text_as_html
from tests._pdf_fixtures import build_pdf


class TestIsPdfResponse:
    def test_content_type_header_is_the_primary_signal(self):
        assert is_pdf_response("application/pdf", "https://example.com/list")
        assert is_pdf_response("application/pdf; charset=binary", "https://example.com/list")

    def test_url_suffix_is_a_fallback_for_a_mislabeled_server(self):
        assert is_pdf_response("application/octet-stream", "https://example.com/subprocessors.pdf")
        assert is_pdf_response("text/plain", "https://example.com/list.pdf?v=2")

    def test_an_ordinary_html_page_is_not_a_pdf(self):
        assert not is_pdf_response("text/html; charset=utf-8", "https://example.com/subprocessors")


class TestExtractPdfText:
    def test_extracts_real_text_from_a_valid_pdf(self):
        pdf = build_pdf("Amazon Web Services - hosting", "Cloudflare, Inc. - CDN")
        text = extract_pdf_text(pdf)
        assert "Amazon Web Services - hosting" in text
        assert "Cloudflare, Inc. - CDN" in text

    def test_preserves_line_structure_across_multiple_rows(self):
        """diff quality depends on one entity per line, not the whole
        document collapsed onto one — see normalizer.py's NORMALIZER_VERSION
        history for what happens when that isn't true."""
        pdf = build_pdf("Row one", "Row two", "Row three")
        text = extract_pdf_text(pdf)
        assert text.splitlines() == ["Row one", "Row two", "Row three"]

    def test_a_corrupt_pdf_raises_rather_than_returning_garbage(self):
        import pytest

        with pytest.raises(Exception):
            extract_pdf_text(b"not actually a pdf")


class TestPdfTextAsHtml:
    def test_feeds_the_existing_normalizer_and_keeps_line_breaks(self):
        """The whole point: no changes needed to normalizer.py, monitoring.py
        or directory.py — a PDF just has to arrive looking like HTML that
        already breaks lines in the right place."""
        pdf = build_pdf("Amazon Web Services - hosting", "Cloudflare, Inc. - CDN")
        html = pdf_text_as_html(extract_pdf_text(pdf))

        canonical = HTMLNormalizer().normalize(html)
        assert canonical.splitlines() == [
            "Amazon Web Services - hosting",
            "Cloudflare, Inc. - CDN",
        ]

    def test_escapes_html_special_characters(self):
        html = pdf_text_as_html("Acme <Corp> & Sons")
        assert "<Corp>" not in html
        assert "&amp;" in html

    def test_blank_lines_are_dropped(self):
        html = pdf_text_as_html("first\n\n\nsecond")
        assert html.count("<p>") == 2

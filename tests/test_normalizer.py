from app.core.scraper.normalizer import HTMLNormalizer

_n = HTMLNormalizer()


def test_strips_noise_tags():
    html = "<html><body><script>alert(1)</script><p>Policy text</p><footer>foot</footer></body></html>"
    assert _n.normalize(html) == "Policy text"


def test_strips_cookie_banners():
    html = '<body><div class="cookie-consent">Accept cookies</div><p>Real content</p></body>'
    out = _n.normalize(html)
    assert "Accept cookies" not in out
    assert "Real content" in out


def test_masks_hex_tokens():
    token = "a" * 40
    html = f"<body><p>session {token} end</p></body>"
    out = _n.normalize(html)
    assert token not in out
    assert "[HASH]" in out


def test_collapses_whitespace():
    html = "<body><p>one</p>\n\n   <p>two</p></body>"
    assert _n.normalize(html) == "one two"


def test_empty_html_returns_empty_string():
    assert _n.normalize("") == ""
    assert _n.normalize("<html><body></body></html>") == ""

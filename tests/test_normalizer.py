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


def test_each_block_becomes_its_own_line():
    """Line structure is what makes a line diff mean anything — see
    normalizer.NORMALIZER_VERSION and detector.py."""
    html = "<body><p>one</p>\n\n   <p>two</p></body>"
    assert _n.normalize(html) == "one\ntwo"


def test_whitespace_inside_a_block_still_collapses():
    html = "<body><p>one    two\n\n   three</p></body>"
    assert _n.normalize(html) == "one two three"


def test_a_table_row_stays_on_one_line():
    """A sub-processor row is one record. Splitting its cells across lines
    would smear a single added vendor over several diff lines."""
    html = "<body><table><tr><td>Acme</td><td>hosting</td><td>EU</td></tr></table></body>"
    assert _n.normalize(html) == "Acme hosting EU"


def test_empty_html_returns_empty_string():
    assert _n.normalize("") == ""
    assert _n.normalize("<html><body></body></html>") == ""

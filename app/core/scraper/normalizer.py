import re

from selectolax.parser import HTMLParser

_NOISE_TAGS = frozenset(
    ["script", "style", "nav", "footer", "header", "noscript", "iframe", "svg", "form", "button", "aside"]
)

_BANNER_KEYWORDS = re.compile(
    r"cookie|consent|privacy[\-_]banner|gdpr|notice[\-_]banner",
    re.IGNORECASE,
)

# Matches 32–64 char hex strings (session IDs, CSRF tokens, nonces)
_HEX_TOKEN = re.compile(r"\b[0-9a-f]{32,64}\b", re.IGNORECASE)

# Matches query-string tokens like ?token=abc123... or &nonce=...
_QUERY_TOKEN = re.compile(r"([?&](?:token|nonce|csrf|sid|session)[=][^\s&\"']+)", re.IGNORECASE)


class HTMLNormalizer:
    """Converts raw HTML into a stable, noise-free plaintext for diffing."""

    def normalize(self, html: str) -> str:
        tree = HTMLParser(html)

        self._remove_noise_tags(tree)
        self._remove_banner_elements(tree)

        body = tree.body or tree.root
        text = body.text(separator=" ") if body else ""

        text = re.sub(r"\s+", " ", text).strip()
        text = _HEX_TOKEN.sub("[HASH]", text)
        text = _QUERY_TOKEN.sub("", text)

        return text

    def _remove_noise_tags(self, tree: HTMLParser) -> None:
        for tag in _NOISE_TAGS:
            for node in tree.css(tag):
                node.decompose()

    def _remove_banner_elements(self, tree: HTMLParser) -> None:
        for node in tree.css("[id],[class]"):
            id_val = node.attributes.get("id") or ""
            class_val = node.attributes.get("class") or ""
            if _BANNER_KEYWORDS.search(id_val) or _BANNER_KEYWORDS.search(class_val):
                node.decompose()

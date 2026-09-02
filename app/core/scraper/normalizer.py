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

# Bumped whenever normalize() changes shape in a way that moves the hash of
# an unchanged page. Stored per source (subprocessors/vendors
# .content_format_version) so the sweep can tell "this page changed" from
# "we changed how we read pages" and silently re-baseline instead of
# inventing a change event — and, on the tenant side, emailing every
# customer's subscribers about a change that never happened.
#
# 1: whole document collapsed onto a single line.
# 2: one line per block element (2026-09-02).
NORMALIZER_VERSION = 2

# Entering one of these ends the current line. Anything else is inline and
# stays on the line it started.
_LINE_BREAK_TAGS = frozenset(
    [
        "p", "div", "br", "hr", "section", "article", "main",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "dl", "dt", "dd",
        "table", "thead", "tbody", "tfoot", "tr", "caption",
        "blockquote", "pre", "figure", "figcaption", "address",
    ]
)

# Cells are deliberately NOT line breaks: a sub-processor table row is one
# record, and keeping "Acme Inc | hosting | EU" on one line is what makes a
# line-based diff say "this vendor was added" instead of smearing the change
# across three lines of context.
_CELL_TAGS = frozenset(["td", "th"])


class HTMLNormalizer:
    """Converts raw HTML into a stable, noise-free plaintext for diffing."""

    def normalize(self, html: str) -> str:
        """Plain text, one line per block element.

        The line structure is the entire point. Before 2026-09-02 this
        collapsed every newline into a space, and detector.py then ran
        splitlines() over the result — which, on a document with no
        newlines in it, returns a single element. difflib was therefore
        always comparing two one-line "files", so its output could only
        ever be "the whole document was deleted, the whole document was
        added", for a one-word typo as much as for a new sub-processor.

        That made the unified diff in every evidence pack unreadable, and
        made the 12k-character cut fed to the classifier a blind head-crop
        of the old document rather than a view of what changed.
        """
        tree = HTMLParser(html)

        self._remove_noise_tags(tree)
        self._remove_banner_elements(tree)

        body = tree.body or tree.root
        text = self._to_block_lines(body) if body else ""

        text = _HEX_TOKEN.sub("[HASH]", text)
        text = _QUERY_TOKEN.sub("", text)

        return text

    def _to_block_lines(self, body) -> str:
        lines: list[str] = []
        current: list[str] = []

        def _flush() -> None:
            # All whitespace inside a block collapses, newlines included:
            # a newline in the source HTML is layout, not structure.
            # Structure comes only from the block tags below.
            joined = re.sub(r"\s+", " ", " ".join(current)).strip()
            current.clear()
            if joined:
                lines.append(joined)

        for node in body.traverse(include_text=True):
            tag = node.tag
            if tag == "-text":
                chunk = node.text(deep=False) or ""
                if chunk.strip():
                    current.append(chunk)
            elif tag in _LINE_BREAK_TAGS:
                _flush()
            elif tag in _CELL_TAGS:
                # Keep the row together, but never let two cells run into
                # one word.
                current.append(" ")

        _flush()
        return "\n".join(lines)

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

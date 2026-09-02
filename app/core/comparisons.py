"""The parts of /compare that are not language-specific.

The category copy itself moved into `locales/<lang>.json` when the page was
translated — four languages, four versions of every sentence, so keeping a
fifth copy here would guarantee that editing one of them changed nothing on
the page. What stays is what is the same in every language: our own pricing
line, the date the figures were checked, and the old per-competitor slugs
that still have to redirect.

The page is deliberately nameless. Naming a competitor of our own size on
our own site advertises them to a visitor who had not heard of them, so the
copy describes shapes of product instead — a rule enforced by a test that
reads every locale file.

Update `VERIFIED_ON` and the figures in the locale files together; a stale
price on a comparison page is the first thing a reader catches.
"""

VERIFIED_ON = "1 September 2026"

OURS = {
    "free": "3 vendor pages, permanently",
    "paid": "$99/month for 25 pages",
}

# The old per-competitor URLs, kept as redirect targets so links and any
# indexed pages do not 404. Never rendered as copy.
LEGACY_SLUGS = ("registora", "dpaflow", "pagecrawl")

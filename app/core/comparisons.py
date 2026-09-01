"""Comparison page content.

Every claim here was read off the competitor's own live site on 1 September
2026 and each page says so. Prices in this category move, and a comparison
page that is quietly wrong is worse than none — it is the first thing a
prospect checks. `verified_on` is shown to the reader; update it and the
figures together, never one alone.

The honest column matters as much as the flattering one: `they_win` is not
decoration. A buyer who finds the weakness themselves stops believing the
rest of the page.
"""
from dataclasses import dataclass, field

VERIFIED_ON = "1 September 2026"

OURS = {
    "free": "3 vendor pages, permanently",
    "paid": "$99/month for 25 pages",
    "monitoring": "Daily, with a browser fallback for JavaScript-rendered pages",
}


@dataclass(frozen=True)
class Comparison:
    slug: str
    name: str
    url: str
    tagline: str
    # One-line answer to "should I read on?"
    verdict: str
    pricing: str
    rows: list[tuple[str, str, str]] = field(default_factory=list)
    they_win: list[str] = field(default_factory=list)
    we_win: list[str] = field(default_factory=list)


COMPARISONS: dict[str, Comparison] = {
    "registora": Comparison(
        slug="registora",
        name="Registora",
        url="https://registora.com/",
        tagline="The subprocessor page that keeps itself current",
        verdict=(
            "The closest product to ours, and cheaper. Choose Registora if you want unlimited "
            "vendors on a small budget; choose TrustPages if the review trail matters more than "
            "the vendor count."
        ),
        pricing="Free for 5 (with their wordmark on your page), $19/month for 15, $49/month unlimited",
        rows=[
            ("Permanent free tier", "5 pages, page carries their wordmark", "3 pages, no wordmark"),
            ("Paid price", "$19 or $49 per month", "$99 per month for 25 pages"),
            ("Monitoring frequency", "Daily", "Daily"),
            ("Public trust page", "Yes, on a custom subdomain from $19", "Yes, on a usetrustpages.com path"),
            ("Article 28(2) notice", "Yes, drafted automatically", "Yes, drafted per change on the Growth plan"),
            ("Review before publishing", "Notices are drafted for approval", "Every material change queues for approval; only high-confidence cosmetic edits auto-publish"),
            ("Stored page text", "Not published on their site", "Both documents kept per change, with hashes"),
            ("Audit export", "CSV on the $49 tier", "CSV on every plan, free included"),
            ("Slack alerts", "Yes, on the $49 tier", "No — email only"),
            ("API", "Yes", "No"),
            ("DORA XBRL export", "Listed as coming soon", "No"),
        ],
        they_win=[
            "Unlimited vendors for $49 — we cap Growth at 25 for $99.",
            "A custom subdomain from $19; our trust page lives on a usetrustpages.com path.",
            "Slack alerts and an API, neither of which we have.",
            "A far larger published library of vendor pages and guides.",
        ],
        we_win=[
            "Every change is classified material or cosmetic before it reaches you, and only "
            "high-confidence cosmetic edits publish themselves. You review the rest.",
            "The full page text is kept on both sides of every change, with content hashes — "
            "so “what did this page say in March” has an answer, not just a diff.",
            "CSV export of the whole history is on the free plan, not held back for a paid tier.",
            "Any URL can be monitored, with a real browser when the page needs one. Vendor "
            "coverage is not limited to a curated list.",
        ],
    ),
    "dpaflow": Comparison(
        slug="dpaflow",
        name="DPAFlow",
        url="https://dpaflow.com/",
        tagline="Vendor and subprocessor changes, detected the moment they happen",
        verdict=(
            "Same job, aimed at a privacy team with a budget and a headcount. If several people "
            "review changes and you need RoPA and TIA modules alongside, DPAFlow is built for "
            "that. If one person owns this, their review workflow costs €299 and ours is $99."
        ),
        pricing="€99/month Starter, €299/month Professional, €999/month Business; 7-day trial",
        rows=[
            ("Permanent free tier", "None — 7-day trial", "3 pages, permanently"),
            ("Entry price", "€99/month, monitoring and evidence only", "$99/month, everything below included"),
            ("Review workflow", "€299/month tier", "Included"),
            ("Audit export", "€299/month tier", "Included on every plan"),
            ("Public trust page", "No — the evidence faces inward", "Yes, with customer subscriptions"),
            ("Article 28(2) notice", "Not offered", "Drafted per change"),
            ("Multiple users and roles", "Yes, on the €999 tier", "No — one owner per account"),
            ("RoPA / TIA modules", "Yes, on the €999 tier", "No"),
            ("EU data residency", "Yes, stated", "Hosted in Frankfurt, not contractually offered"),
        ],
        they_win=[
            "Role-based access for a privacy, legal and procurement team; we have one login per account.",
            "RoPA and Transfer Impact Assessment modules — we do not touch either.",
            "Stated EU-first hosting and a DPA available before purchase.",
        ],
        we_win=[
            "The review queue and the audit export are in the $99 plan. Theirs start at €299.",
            "A public trust page your customers can subscribe to — DPAFlow's evidence faces "
            "inward, at the auditor, not at your buyers.",
            "A drafted Article 28(2) customer notice for each change.",
            "A permanent free tier instead of a 7-day trial.",
        ],
    ),
    "pagecrawl": Comparison(
        slug="pagecrawl",
        name="PageCrawl.io",
        url="https://pagecrawl.io/",
        tagline="Monitor web pages, get AI summaries of what changed",
        verdict=(
            "A good general page-change monitor that many teams point at a sub-processor list. "
            "It will tell you the page moved. It will not give you anything to hand an auditor."
        ),
        pricing="Free for 6 pages at hourly checks, $13.33/month for 200, up to $83.25/month for 1,000",
        rows=[
            ("What it is", "General page-change monitoring", "Sub-processor compliance monitoring"),
            ("Free tier", "6 pages, checked hourly", "3 pages, checked daily"),
            ("Price for volume", "200 pages for $13.33/month", "25 pages for $99/month"),
            ("Change classification", "AI importance score, 0-100", "Material / cosmetic / uncertain, with an approval queue"),
            ("Alert channels", "Slack, Teams, Discord, Telegram, email, webhook", "Email"),
            ("Public trust page", "No", "Yes, with customer subscriptions"),
            ("Evidence for an audit", "No", "Both page documents, hashes, decision trail, CSV export"),
            ("Article 28(2) notice", "No", "Drafted per change"),
        ],
        they_win=[
            "Far cheaper per page, and far more of them — 200 pages for the price of a lunch.",
            "Six alert channels to our one.",
            "Element-level selectors and auto-discovery of new pages.",
        ],
        we_win=[
            "The output is compliance evidence, not a notification: dated documents, hashes, "
            "who approved what, exportable as CSV.",
            "A public trust page that answers the question your customers' security "
            "questionnaires ask.",
            "A drafted Article 28(2) customer notice for each change.",
        ],
    ),
}

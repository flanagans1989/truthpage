"""Content for /compare.

Deliberately nameless. Naming a competitor of our own size on our own site
advertises them to a visitor who had not heard of them — the tactic only pays
when you are renting the search volume of someone far bigger. So this page
describes the shapes of tool a buyer actually meets and says plainly which
one to pick, without turning our page into their billboard.

The figures are category ranges read off live vendor sites on the date below,
not quotes attributed to anyone. Update `VERIFIED_ON` and the numbers
together; a stale price on a comparison page is the first thing a reader
catches. Names for our own reference stay in GROWTH.md, not here.
"""
from dataclasses import dataclass, field

VERIFIED_ON = "1 September 2026"

OURS = {
    "free": "3 vendor pages, permanently",
    "paid": "$99/month for 25 pages",
}


@dataclass(frozen=True)
class Category:
    slug: str
    name: str
    # What the buyer sees when they land on one of these.
    shape: str
    price: str
    strengths: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    pick_them_when: str = ""


CATEGORIES: list[Category] = [
    Category(
        slug="lightweight-registries",
        name="Lightweight subprocessor registries",
        shape=(
            "A hosted page listing your sub-processors, refreshed by daily checks of the "
            "vendors you name. The closest neighbours to what we do."
        ),
        price="Free for a handful of vendors, roughly $19-$49/month for more or unlimited",
        strengths=[
            "Cheapest route to unlimited vendors, by a wide margin",
            "Custom subdomain for the public page at the lower paid tiers",
            "Free tiers exist, though they usually carry the vendor's own mark on your page",
        ],
        limits=[
            "The record is generally the current state plus alerts, not a dated document per change",
            "Review before publishing is thin or absent — updates tend to flow automatically",
            "Coverage is limited to the vendors the tool already tracks",
        ],
        pick_them_when=(
            "You have a long vendor list, a small budget, and nobody is going to ask you to "
            "prove what a page said last quarter."
        ),
    ),
    Category(
        slug="privacy-suites",
        name="Privacy-team evidence suites",
        shape=(
            "Built for a privacy function with several people in it: monitoring plus review "
            "queues, evidence capture, and records-of-processing and transfer-assessment modules."
        ),
        price="Around €99/month entry, €299 for the review workflow, €999 for roles and modules",
        strengths=[
            "Role-based access for privacy, legal and procurement working the same queue",
            "RoPA and Transfer Impact Assessment alongside the monitoring",
            "Stated EU data residency and a DPA available before purchase",
        ],
        limits=[
            "The review workflow and audit export sit two tiers up, not in the entry plan",
            "The evidence faces inward, at your auditor — there is no public page for your customers",
            "Trials are short and there is no permanent free plan",
        ],
        pick_them_when=(
            "More than one person reviews vendor changes, or you need RoPA and TIA in the "
            "same tool. We cannot serve a two-person privacy team; they can."
        ),
    ),
    Category(
        slug="page-monitors",
        name="General page-change monitors",
        shape=(
            "Not compliance products. They watch any URL and tell you it moved, with an AI "
            "summary and an importance score."
        ),
        price="Free for a handful of pages, roughly $13-$85/month for hundreds",
        strengths=[
            "Far cheaper per page, and hundreds of pages rather than dozens",
            "Alerts anywhere — Slack, Teams, Discord, webhooks",
            "Element-level selectors and automatic discovery of new pages",
        ],
        limits=[
            "The output is a notification, not evidence: no decision trail, no audit export",
            "Nothing to show a customer — no public page, no subscriber notice",
            "Nothing drafts the Article 28(2) message your DPA promises",
        ],
        pick_them_when=(
            "You want to know when pages change and you will handle the compliance side "
            "yourself, in a spreadsheet you already keep."
        ),
    ),
    Category(
        slug="trust-platforms",
        name="Trust centre and GRC platforms",
        shape=(
            "The enterprise end: a full trust centre with questionnaire automation, "
            "certifications, NDA-gated documents, and sub-processors as one section of many."
        ),
        price="Typically annual contracts, four to five figures",
        strengths=[
            "Answers the entire security review, not only the sub-processor part",
            "Document libraries, access controls, integrations with the rest of the stack",
            "The name on the page carries weight with an enterprise buyer",
        ],
        limits=[
            "Priced and scoped for a company with a compliance function",
            "Sub-processor monitoring is a feature, not the focus, and is often manual",
            "Weeks to deploy rather than an afternoon",
        ],
        pick_them_when=(
            "Security questionnaires are a recurring cost across your whole company and you "
            "have the budget to solve all of it at once."
        ),
    ),
]

# What we actually do differently, stated without reference to anyone else.
OUR_POSITION: list[tuple[str, str]] = [
    (
        "The documents, not just the diff",
        "Every detected change stores the vendor's page as it read before and after, each with "
        "a content hash and a timestamp, plus who reviewed it and when. “What did this page "
        "say in March” has an answer.",
    ),
    (
        "Nothing publishes without you",
        "Changes are classified material or cosmetic, and only high-confidence cosmetic edits "
        "publish themselves. Everything else waits in a queue with a side-by-side diff.",
    ),
    (
        "Export on every plan",
        "The whole history leaves as one CSV — dates, vendors, classifications, hashes, "
        "decisions — including on the free plan. It is the file you actually get asked for.",
    ),
    (
        "The customer notice, drafted",
        "Your DPA promises customers a heads-up under Article 28(2). We draft it from the "
        "change itself, so the step that usually gets skipped is a review rather than a "
        "blank page.",
    ),
    (
        "Any URL, including the awkward ones",
        "Pages that only render with JavaScript are fetched with a real browser, so coverage "
        "is not limited to a list of vendors we happen to track.",
    ),
]

# Where we are honestly weaker. A comparison page that only flatters us does
# not survive the reader checking one line of it.
OUR_GAPS: list[str] = [
    "25 pages on the paid plan, where cheaper tools offer unlimited.",
    "The public trust page lives on a usetrustpages.com address; there is no custom domain yet.",
    "Email alerts only — no Slack, no webhooks, no API.",
    "One login per account: no roles for a privacy team working together.",
    "No RoPA, no Transfer Impact Assessments, no questionnaire automation.",
]

# The old per-competitor URLs, kept as redirects so links and any indexed
# pages do not 404.
LEGACY_SLUGS = ("registora", "dpaflow", "pagecrawl")

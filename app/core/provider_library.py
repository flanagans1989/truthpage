"""The 30 providers a small SaaS company actually lists in its own DPA.

The point of this file is the first ninety seconds of the product. Typing a
name and hunting down the vendor's sub-processor URL is the step where a new
signup gives up, and it is a step nobody should have to do twice: the URLs
are the same for every customer, so they belong in the codebase, not in each
tenant's head.

`verified` means the directory sweep has actually fetched that page and read
a sub-processor list off it (see `app.services.directory`). An unverified
entry is a best-effort URL — it may 404 or point at a page with no list, in
which case the tenant simply gets no changes rather than a wrong page. The
flag is shown in the picker so nobody is misled about which is which.

`accent` is a Tailwind class pair for the monogram tile. Real logos are
deliberately not hotlinked: it would put a third-party request (and the
tenant's IP) on our dashboard for every card, break whenever a CDN moves,
and put us on the wrong side of trademark use. Initials render instantly and
never 404.
"""

# slug is the picker's checkbox value and must stay stable — it is what a
# `?vendor=` link from the public directory arrives with.
PROVIDERS: list[dict] = [
    {"slug": "aws", "name": "Amazon Web Services", "url": "https://aws.amazon.com/compliance/sub-processors/",
     "description": "Cloud hosting and infrastructure", "category": "Infrastructure",
     "accent": "bg-orange-100 text-orange-700", "verified": True},
    {"slug": "google-cloud", "name": "Google Cloud", "url": "https://cloud.google.com/terms/subprocessors",
     "description": "Cloud hosting and infrastructure", "category": "Infrastructure",
     "accent": "bg-blue-100 text-blue-700", "verified": True},
    {"slug": "cloudflare", "name": "Cloudflare", "url": "https://www.cloudflare.com/gdpr/subprocessors/cloudflare-services/",
     "description": "CDN, DNS and DDoS protection", "category": "Infrastructure",
     "accent": "bg-amber-100 text-amber-700", "verified": True},
    {"slug": "vercel", "name": "Vercel", "url": "https://vercel.com/legal/sub-processors",
     "description": "Frontend hosting and deployment", "category": "Infrastructure",
     "accent": "bg-slate-200 text-slate-800", "verified": False},
    {"slug": "netlify", "name": "Netlify", "url": "https://www.netlify.com/legal/subprocessors/",
     "description": "Frontend hosting and deployment", "category": "Infrastructure",
     "accent": "bg-teal-100 text-teal-700", "verified": False},
    {"slug": "digitalocean", "name": "DigitalOcean", "url": "https://www.digitalocean.com/trust/subprocessors",
     "description": "Cloud servers and managed databases", "category": "Infrastructure",
     "accent": "bg-sky-100 text-sky-700", "verified": False},
    {"slug": "heroku", "name": "Heroku", "url": "https://compliance.salesforce.com/en/documents/a00Kd00000z7FAnIAM",
     "description": "Application hosting", "category": "Infrastructure",
     "accent": "bg-violet-100 text-violet-700", "verified": False},

    {"slug": "supabase", "name": "Supabase", "url": "https://supabase.com/legal/customer-resources/subprocessor-list",
     "description": "Managed Postgres, auth and storage", "category": "Data",
     "accent": "bg-emerald-100 text-emerald-700", "verified": False},
    {"slug": "mongodb", "name": "MongoDB", "url": "https://www.mongodb.com/products/platform/trust/subprocessors",
     "description": "Managed database", "category": "Data",
     "accent": "bg-green-100 text-green-700", "verified": False},
    {"slug": "snowflake", "name": "Snowflake", "url": "https://trust.snowflake.com/?product=subprocessors",
     "description": "Data warehouse", "category": "Data",
     "accent": "bg-cyan-100 text-cyan-700", "verified": False},
    {"slug": "databricks", "name": "Databricks", "url": "https://www.databricks.com/legal/databricks-subprocessors",
     "description": "Data and analytics platform", "category": "Data",
     "accent": "bg-red-100 text-red-700", "verified": True},

    {"slug": "stripe", "name": "Stripe", "url": "https://stripe.com/legal/service-providers",
     "description": "Payment processing", "category": "Payments",
     "accent": "bg-indigo-100 text-indigo-700", "verified": True},
    {"slug": "paddle", "name": "Paddle", "url": "https://trust.paddle.com/subprocessors",
     "description": "Payments and merchant of record", "category": "Payments",
     "accent": "bg-blue-100 text-blue-700", "verified": False},
    {"slug": "shopify", "name": "Shopify", "url": "https://help.shopify.com/en/manual/privacy-and-security/privacy/subprocessors",
     "description": "Commerce platform", "category": "Payments",
     "accent": "bg-lime-100 text-lime-700", "verified": False},

    {"slug": "openai", "name": "OpenAI", "url": "https://openai.com/policies/sub-processor-list/",
     "description": "AI model API", "category": "AI",
     "accent": "bg-slate-200 text-slate-800", "verified": False},
    {"slug": "anthropic", "name": "Anthropic", "url": "https://www.anthropic.com/legal/subprocessors",
     "description": "AI model API", "category": "AI",
     "accent": "bg-orange-100 text-orange-700", "verified": False},

    {"slug": "resend", "name": "Resend", "url": "https://resend.com/legal/subprocessors",
     "description": "Transactional email", "category": "Email",
     "accent": "bg-slate-200 text-slate-800", "verified": True},
    {"slug": "postmark", "name": "Postmark", "url": "https://postmarkapp.com/eu-privacy",
     "description": "Transactional email", "category": "Email",
     "accent": "bg-yellow-100 text-yellow-700", "verified": True},
    {"slug": "sendgrid", "name": "SendGrid", "url": "https://www.twilio.com/en-us/legal/sub-processors",
     "description": "Transactional and marketing email", "category": "Email",
     "accent": "bg-blue-100 text-blue-700", "verified": True},
    {"slug": "mailchimp", "name": "Mailchimp", "url": "https://mailchimp.com/legal/subprocessors/",
     "description": "Marketing email", "category": "Email",
     "accent": "bg-yellow-100 text-yellow-700", "verified": False},
    {"slug": "twilio", "name": "Twilio", "url": "https://www.twilio.com/en-us/legal/sub-processors",
     "description": "SMS and voice", "category": "Email",
     "accent": "bg-red-100 text-red-700", "verified": True},

    {"slug": "sentry", "name": "Sentry", "url": "https://sentry.io/legal/subprocessors/",
     "description": "Error tracking", "category": "Observability",
     "accent": "bg-purple-100 text-purple-700", "verified": True},
    {"slug": "datadog", "name": "Datadog", "url": "https://www.datadoghq.com/legal/subprocessors/",
     "description": "Monitoring and logs", "category": "Observability",
     "accent": "bg-violet-100 text-violet-700", "verified": False},
    {"slug": "segment", "name": "Segment", "url": "https://www.twilio.com/en-us/legal/sub-processors",
     "description": "Customer data pipeline", "category": "Observability",
     "accent": "bg-green-100 text-green-700", "verified": True},
    {"slug": "amplitude", "name": "Amplitude", "url": "https://amplitude.com/subprocessor-list",
     "description": "Product analytics", "category": "Observability",
     "accent": "bg-blue-100 text-blue-700", "verified": False},

    {"slug": "okta", "name": "Okta", "url": "https://www.okta.com/legal/trustandcompliance/subprocessors/",
     "description": "Single sign-on and identity", "category": "Identity",
     "accent": "bg-sky-100 text-sky-700", "verified": False},

    {"slug": "slack", "name": "Slack", "url": "https://slack.com/slack-subprocessors",
     "description": "Team messaging", "category": "Workplace",
     "accent": "bg-fuchsia-100 text-fuchsia-700", "verified": False},
    {"slug": "atlassian", "name": "Atlassian", "url": "https://www.atlassian.com/legal/subprocessors",
     "description": "Jira, Confluence and Bitbucket", "category": "Workplace",
     "accent": "bg-blue-100 text-blue-700", "verified": True},
    {"slug": "notion", "name": "Notion", "url": "https://trust.notion.com/subprocessors",
     "description": "Docs and internal wiki", "category": "Workplace",
     "accent": "bg-slate-200 text-slate-800", "verified": False},
    {"slug": "intercom", "name": "Intercom", "url": "https://www.intercom.com/legal/subprocessors-list",
     "description": "Customer support and messaging", "category": "Workplace",
     "accent": "bg-indigo-100 text-indigo-700", "verified": False},
    {"slug": "hubspot", "name": "HubSpot", "url": "https://legal.hubspot.com/sub-processors-page",
     "description": "CRM and marketing", "category": "Workplace",
     "accent": "bg-orange-100 text-orange-700", "verified": False},
]

# Auth0 deliberately isn't a row here: since the Okta acquisition its old
# docs.auth0.com subprocessors page 404s, and Okta only republished its own
# list under that name, not a distinct Auth0 one. A pasted policy naming
# Auth0 falls through to "give us the URL" instead of silently monitoring
# Okta's page under Auth0's name.

# Order the picker puts the groups in. A first-time reader scans for their
# host before their CRM, so infrastructure leads.
CATEGORY_ORDER = [
    "Infrastructure", "Data", "Payments", "AI", "Email",
    "Observability", "Identity", "Workplace",
]

BY_SLUG: dict[str, dict] = {p["slug"]: p for p in PROVIDERS}

# Lookup for the paste-your-policy importer: an extracted name like
# "Amazon Web Services, Inc." has to find the AWS row. Keys are lowercase and
# cover the short forms vendors actually write in their own tables.
_ALIASES: dict[str, str] = {
    "amazon web services": "aws",
    "amazon aws": "aws",
    "amazon": "aws",
    "google cloud platform": "google-cloud",
    "google cloud": "google-cloud",
    "google": "google-cloud",
    "gcp": "google-cloud",
    "google workspace": "google-cloud",
    "twilio sendgrid": "sendgrid",
    "twilio segment": "segment",
    "segment.io": "segment",
    "mongodb atlas": "mongodb",
    "openai llc": "openai",
    "atlassian corporation": "atlassian",
    "jira": "atlassian",
    "confluence": "atlassian",
    "salesforce": "heroku",
    "postmarkapp": "postmark",
    "stripe payments": "stripe",
    "amazon web services emea": "aws",
}

_LEGAL_SUFFIXES = (
    " inc.", " inc", " llc", " l.l.c.", " ltd.", " ltd", " limited", " gmbh",
    " b.v.", " bv", " corporation", " corp.", " corp", " plc", " pbc", " s.a.",
    " sarl", " pte. ltd.", " pty ltd", " co.", " ag",
)


def normalise_name(name: str) -> str:
    """Lowercase, drop punctuation noise and the company-form suffix.

    "Stripe, Inc." and "stripe" have to land on the same key, or a pasted
    policy re-adds a vendor the tenant already monitors.
    """
    cleaned = " ".join((name or "").lower().replace(",", " ").split())
    changed = True
    while changed:
        changed = False
        for suffix in _LEGAL_SUFFIXES:
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                changed = True
    return cleaned.strip(" .")


def match_provider(name: str) -> dict | None:
    """The library row an extracted or typed vendor name refers to, or None.

    Exact-ish only: an alias table and a normalised name, no fuzzy distance.
    A wrong match silently points the tenant's monitoring at a different
    company's policy page, which is worse than asking them for the URL.
    """
    key = normalise_name(name)
    if not key:
        return None
    if key in BY_SLUG:
        return BY_SLUG[key]
    if key in _ALIASES:
        return BY_SLUG[_ALIASES[key]]
    for provider in PROVIDERS:
        if normalise_name(provider["name"]) == key:
            return provider
    return None


def grouped() -> list[tuple[str, list[dict]]]:
    """Providers by category, in CATEGORY_ORDER, for the picker."""
    return [
        (category, [p for p in PROVIDERS if p["category"] == category])
        for category in CATEGORY_ORDER
    ]

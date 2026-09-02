"""Candidate pages for the public directory.

A candidate, not a promise. Nothing here is published until a check has
actually fetched the page and the extractor has read a list off it — see
`services.directory.run_vendor_check`. A wrong URL therefore costs one
failed fetch and never becomes a broken public page, which is why this list
can be long and unverified rather than short and hand-checked.

Ordered by how often the name turns up in a small SaaS company's own
sub-processor list: those are the queries worth ranking for.
"""

VENDOR_SEEDS: list[dict[str, str]] = [
    {"slug": "stripe", "name": "Stripe", "monitored_url": "https://stripe.com/legal/service-providers", "homepage_url": "https://stripe.com"},
    {"slug": "openai", "name": "OpenAI", "monitored_url": "https://openai.com/policies/sub-processor-list/", "homepage_url": "https://openai.com"},
    {"slug": "anthropic", "name": "Anthropic", "monitored_url": "https://www.anthropic.com/legal/subprocessors", "homepage_url": "https://www.anthropic.com"},
    {"slug": "aws", "name": "Amazon Web Services", "monitored_url": "https://aws.amazon.com/compliance/sub-processors/", "homepage_url": "https://aws.amazon.com"},
    {"slug": "google-cloud", "name": "Google Cloud", "monitored_url": "https://cloud.google.com/terms/subprocessors", "homepage_url": "https://cloud.google.com"},
    {"slug": "cloudflare", "name": "Cloudflare", "monitored_url": "https://www.cloudflare.com/gdpr/subprocessors/cloudflare-services/", "homepage_url": "https://www.cloudflare.com"},
    {"slug": "vercel", "name": "Vercel", "monitored_url": "https://vercel.com/legal/sub-processors", "homepage_url": "https://vercel.com"},
    {"slug": "github", "name": "GitHub", "monitored_url": "https://docs.github.com/en/site-policy/privacy-policies/github-subprocessors", "homepage_url": "https://github.com"},
    {"slug": "slack", "name": "Slack", "monitored_url": "https://slack.com/slack-subprocessors", "homepage_url": "https://slack.com"},
    {"slug": "notion", "name": "Notion", "monitored_url": "https://trust.notion.com/subprocessors", "homepage_url": "https://www.notion.com"},
    {"slug": "hubspot", "name": "HubSpot", "monitored_url": "https://legal.hubspot.com/sub-processors-page", "homepage_url": "https://www.hubspot.com"},
    {"slug": "twilio", "name": "Twilio", "monitored_url": "https://www.twilio.com/en-us/legal/sub-processors", "homepage_url": "https://www.twilio.com"},
    {"slug": "sendgrid", "name": "SendGrid", "monitored_url": "https://www.twilio.com/en-us/legal/sub-processors", "homepage_url": "https://sendgrid.com"},
    {"slug": "datadog", "name": "Datadog", "monitored_url": "https://www.datadoghq.com/legal/subprocessors/", "homepage_url": "https://www.datadoghq.com"},
    {"slug": "sentry", "name": "Sentry", "monitored_url": "https://sentry.io/legal/subprocessors/", "homepage_url": "https://sentry.io"},
    {"slug": "intercom", "name": "Intercom", "monitored_url": "https://www.intercom.com/legal/subprocessors-list", "homepage_url": "https://www.intercom.com"},
    {"slug": "zendesk", "name": "Zendesk", "monitored_url": "https://support.zendesk.com/hc/en-us/articles/4408883061530-Sub-processor-Policy", "homepage_url": "https://www.zendesk.com"},
    {"slug": "mailchimp", "name": "Mailchimp", "monitored_url": "https://mailchimp.com/legal/subprocessors/", "homepage_url": "https://mailchimp.com"},
    {"slug": "resend", "name": "Resend", "monitored_url": "https://resend.com/legal/subprocessors", "homepage_url": "https://resend.com"},
    {"slug": "postmark", "name": "Postmark", "monitored_url": "https://postmarkapp.com/eu-privacy", "homepage_url": "https://postmarkapp.com"},
    {"slug": "okta", "name": "Okta", "monitored_url": "https://www.okta.com/legal/trustandcompliance/subprocessors/", "homepage_url": "https://www.okta.com"},
    {"slug": "atlassian", "name": "Atlassian", "monitored_url": "https://www.atlassian.com/legal/subprocessors", "homepage_url": "https://www.atlassian.com"},
    {"slug": "asana", "name": "Asana", "monitored_url": "https://asana.com/terms/subprocessors", "homepage_url": "https://asana.com"},
    {"slug": "figma", "name": "Figma", "monitored_url": "https://www.figma.com/sub-processors/", "homepage_url": "https://www.figma.com"},
    {"slug": "linear", "name": "Linear", "monitored_url": "https://trust.linear.app/subprocessors", "homepage_url": "https://linear.app"},
    {"slug": "segment", "name": "Segment", "monitored_url": "https://www.twilio.com/en-us/legal/sub-processors", "homepage_url": "https://segment.com"},
    {"slug": "amplitude", "name": "Amplitude", "monitored_url": "https://amplitude.com/subprocessor-list", "homepage_url": "https://amplitude.com"},
    {"slug": "mixpanel", "name": "Mixpanel", "monitored_url": "https://mixpanel.com/legal/subprocessor-list/", "homepage_url": "https://mixpanel.com"},
    {"slug": "snowflake", "name": "Snowflake", "monitored_url": "https://trust.snowflake.com/?product=subprocessors", "homepage_url": "https://www.snowflake.com"},
    {"slug": "databricks", "name": "Databricks", "monitored_url": "https://www.databricks.com/legal/databricks-subprocessors", "homepage_url": "https://www.databricks.com"},
    {"slug": "mongodb", "name": "MongoDB", "monitored_url": "https://www.mongodb.com/products/platform/trust/subprocessors", "homepage_url": "https://www.mongodb.com"},
    {"slug": "supabase", "name": "Supabase", "monitored_url": "https://supabase.com/legal/customer-resources/subprocessor-list", "homepage_url": "https://supabase.com"},
    {"slug": "netlify", "name": "Netlify", "monitored_url": "https://www.netlify.com/legal/subprocessors/", "homepage_url": "https://www.netlify.com"},
    {"slug": "digitalocean", "name": "DigitalOcean", "monitored_url": "https://www.digitalocean.com/trust/subprocessors", "homepage_url": "https://www.digitalocean.com"},
    {"slug": "heroku", "name": "Heroku", "monitored_url": "https://compliance.salesforce.com/en/documents/a00Kd00000z7FAnIAM", "homepage_url": "https://www.heroku.com"},
    {"slug": "salesforce", "name": "Salesforce", "monitored_url": "https://compliance.salesforce.com/en/documents/a00Kd00000z7FAnIAM", "homepage_url": "https://www.salesforce.com"},
    {"slug": "zoom", "name": "Zoom", "monitored_url": "https://www.zoom.com/en/trust/subprocessors/", "homepage_url": "https://zoom.us"},
    {"slug": "shopify", "name": "Shopify", "monitored_url": "https://help.shopify.com/en/manual/privacy-and-security/privacy/subprocessors", "homepage_url": "https://www.shopify.com"},
    {"slug": "paddle", "name": "Paddle", "monitored_url": "https://trust.paddle.com/subprocessors", "homepage_url": "https://www.paddle.com"},
]

# Auth0 deliberately isn't seeded: since the Okta acquisition its old
# auth0.com/docs subprocessors page 404s, and Okta never republished it as a
# distinct Auth0 list — only Okta's own (a different company's list, wrong
# name on the page) and a rotating trail of dated PDFs under okta.com/sites,
# neither of which this scraper can read a stable list off. Same rule as the
# importer: no confident URL, no entry, rather than a directory page for the
# wrong company.

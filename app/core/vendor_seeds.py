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
    {"slug": "vercel", "name": "Vercel", "monitored_url": "https://vercel.com/legal/subprocessors", "homepage_url": "https://vercel.com"},
    {"slug": "github", "name": "GitHub", "monitored_url": "https://github.com/github/data-protection-agreement/blob/main/GitHub-Data-Protection-Agreement.md", "homepage_url": "https://github.com"},
    {"slug": "slack", "name": "Slack", "monitored_url": "https://slack.com/trust/data-management/subprocessors", "homepage_url": "https://slack.com"},
    {"slug": "notion", "name": "Notion", "monitored_url": "https://www.notion.com/subprocessors", "homepage_url": "https://www.notion.com"},
    {"slug": "hubspot", "name": "HubSpot", "monitored_url": "https://legal.hubspot.com/sub-processors", "homepage_url": "https://www.hubspot.com"},
    {"slug": "twilio", "name": "Twilio", "monitored_url": "https://www.twilio.com/en-us/legal/sub-processors", "homepage_url": "https://www.twilio.com"},
    {"slug": "sendgrid", "name": "SendGrid", "monitored_url": "https://www.twilio.com/en-us/legal/sub-processors", "homepage_url": "https://sendgrid.com"},
    {"slug": "datadog", "name": "Datadog", "monitored_url": "https://www.datadoghq.com/legal/sub-processors/", "homepage_url": "https://www.datadoghq.com"},
    {"slug": "sentry", "name": "Sentry", "monitored_url": "https://sentry.io/legal/subprocessors/", "homepage_url": "https://sentry.io"},
    {"slug": "intercom", "name": "Intercom", "monitored_url": "https://www.intercom.com/legal/subprocessors", "homepage_url": "https://www.intercom.com"},
    {"slug": "zendesk", "name": "Zendesk", "monitored_url": "https://www.zendesk.com/company/subprocessors/", "homepage_url": "https://www.zendesk.com"},
    {"slug": "mailchimp", "name": "Mailchimp", "monitored_url": "https://mailchimp.com/legal/data-processing-addendum/", "homepage_url": "https://mailchimp.com"},
    {"slug": "resend", "name": "Resend", "monitored_url": "https://resend.com/legal/subprocessors", "homepage_url": "https://resend.com"},
    {"slug": "postmark", "name": "Postmark", "monitored_url": "https://postmarkapp.com/eu-privacy", "homepage_url": "https://postmarkapp.com"},
    {"slug": "auth0", "name": "Auth0", "monitored_url": "https://auth0.com/docs/secure/data-privacy-and-compliance/gdpr/subprocessors", "homepage_url": "https://auth0.com"},
    {"slug": "okta", "name": "Okta", "monitored_url": "https://www.okta.com/agreements/#subprocessors", "homepage_url": "https://www.okta.com"},
    {"slug": "atlassian", "name": "Atlassian", "monitored_url": "https://www.atlassian.com/legal/subprocessors", "homepage_url": "https://www.atlassian.com"},
    {"slug": "asana", "name": "Asana", "monitored_url": "https://asana.com/terms/subprocessors", "homepage_url": "https://asana.com"},
    {"slug": "figma", "name": "Figma", "monitored_url": "https://www.figma.com/legal/subprocessors/", "homepage_url": "https://www.figma.com"},
    {"slug": "linear", "name": "Linear", "monitored_url": "https://linear.app/docs/subprocessors", "homepage_url": "https://linear.app"},
    {"slug": "segment", "name": "Segment", "monitored_url": "https://www.twilio.com/en-us/legal/sub-processors", "homepage_url": "https://segment.com"},
    {"slug": "amplitude", "name": "Amplitude", "monitored_url": "https://amplitude.com/legal/sub-processors", "homepage_url": "https://amplitude.com"},
    {"slug": "mixpanel", "name": "Mixpanel", "monitored_url": "https://mixpanel.com/legal/mixpanel-subprocessors/", "homepage_url": "https://mixpanel.com"},
    {"slug": "snowflake", "name": "Snowflake", "monitored_url": "https://www.snowflake.com/en/legal/snowflake-subprocessors/", "homepage_url": "https://www.snowflake.com"},
    {"slug": "databricks", "name": "Databricks", "monitored_url": "https://www.databricks.com/legal/databricks-subprocessors", "homepage_url": "https://www.databricks.com"},
    {"slug": "mongodb", "name": "MongoDB", "monitored_url": "https://www.mongodb.com/legal/subprocessors", "homepage_url": "https://www.mongodb.com"},
    {"slug": "supabase", "name": "Supabase", "monitored_url": "https://supabase.com/legal/subprocessors", "homepage_url": "https://supabase.com"},
    {"slug": "netlify", "name": "Netlify", "monitored_url": "https://www.netlify.com/gdpr-ccpa/", "homepage_url": "https://www.netlify.com"},
    {"slug": "digitalocean", "name": "DigitalOcean", "monitored_url": "https://www.digitalocean.com/legal/sub-processors", "homepage_url": "https://www.digitalocean.com"},
    {"slug": "heroku", "name": "Heroku", "monitored_url": "https://www.salesforce.com/company/privacy/sub-processors/", "homepage_url": "https://www.heroku.com"},
    {"slug": "salesforce", "name": "Salesforce", "monitored_url": "https://www.salesforce.com/company/privacy/sub-processors/", "homepage_url": "https://www.salesforce.com"},
    {"slug": "zoom", "name": "Zoom", "monitored_url": "https://explore.zoom.us/en/subprocessors/", "homepage_url": "https://zoom.us"},
    {"slug": "shopify", "name": "Shopify", "monitored_url": "https://www.shopify.com/legal/subprocessors", "homepage_url": "https://www.shopify.com"},
    {"slug": "paddle", "name": "Paddle", "monitored_url": "https://www.paddle.com/legal/sub-processors", "homepage_url": "https://www.paddle.com"},
]

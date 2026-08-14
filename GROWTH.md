# TrustPages — First 10 Customers Playbook

Objective: 10 paying customers in 30 days. Every task is judged by one question:
**"Will this help us acquire or convert customers within the next 30 days?"**

## Segment

B2B SaaS, 5–50 employees, that **already publish a public sub-processor / DPA page**
but have no trust-center platform (no SafeBase/Vanta). They've proven they have the
problem; the pitch is "who watches that page for changes?"

## Qualification (5 checks; 5/5 = Tier A, 4/5 = Tier B, else skip)

1. Public sub-processor/DPA page exists (findable on Google)
2. No SafeBase/Vanta/Drata trust center (page is static HTML or Notion)
3. 5–50 employees (LinkedIn)
4. Sells B2B (enterprise/security page or SOC2 badge on site)
5. Active in last 6 months (blog/changelog/hiring)

## Where to find prospects

- Google dorks: `inurl:subprocessors`, `inurl:legal/sub-processors`,
  `"sub-processor list" site:notion.site`, `"our sub-processors" -site:paddle.com`
- YC company directory (last 3 batches), Product Hunt B2B launches, G2 rising categories
- Communities: r/SaaS, Indie Hackers, MicroConf Connect

## Weekly loop

- **Mon:** 2h list building → 50 companies into the sheet (company, subprocessor URL,
  founder name, email, tier). Email lookup via Hunter/Apollo free tier.
- **Tue–Thu:** 20–30 emails/day + 10 LinkedIn connects/day. 30 min inbox every morning.
- **Fri:** demos + metrics retro. Reply rate <5% → rewrite message. Demos not converting
  to trials → watch onboarding over screenshare.

## ⚠️ Deliverability rule

Send cold email from a plain Gmail account (studiominhagen@gmail.com), not from
usetrustpages.com/Resend — that domain only carries magic links and customer
notifications, and a spam flag on it would break login for real users. Gmail's normal
sending limits comfortably cover 20–30/day. (Decided 2026-08-14: a secondary domain +
Resend Pro upgrade was considered and skipped as unnecessary at this volume.)

## Email templates

### Tier A (personalized)

Subject: `your sub-processor page`

> Hi {name}, I was looking at {company}'s sub-processor list (the one at {url}) —
> nicely done, most teams your size don't even have one.
>
> Quick question: when one of those vendors quietly adds a new sub-processor, how do
> you find out? Most DPAs promise customers a heads-up, but vendors don't announce changes.
>
> I built TrustPages for exactly this: it watches those pages, flags real changes
> (AI filters the noise), and keeps a public change history your enterprise buyers can
> audit. Our own live page: https://usetrustpages.com/trust/trustpages
>
> Worth a 15-min look? Free 14-day trial, no card.

### Tier B (short)

Subject: `who watches {vendor}'s sub-processors for you?`

> Hi {name} — your DPA likely promises customers you'll flag sub-processor changes,
> but Stripe/AWS/OpenAI change theirs silently. TrustPages monitors them and publishes
> an auditable trust page: https://usetrustpages.com. 14-day free trial, no card. Useful?

### Follow-ups

- **Day +3:** "One thing I forgot — here's what a change alert actually looks like:
  {screenshot}. Takes 5 min to set up."
- **Day +7 (value, not pitch):** "FYI — {their vendor} updated their sub-processor list
  on {date}. Did you catch it?" — detect this with our own system; the product is the
  outreach weapon.
- **Day +14 (close the loop):** "If vendor tracking isn't a priority this quarter, no
  worries. Mind if I check back in 3 months?"

### LinkedIn

- **Connect note:** "Hi {name} — saw {company}'s sub-processor page, rare for a team
  your size. I work on tooling in that exact space, thought it'd be good to connect."
- **After accept:** "Thanks for connecting! Honest question, not a pitch: how do you
  currently find out when a vendor changes their sub-processors? Asking because I built
  something for this and I'm trying to learn how teams handle it today."

## Prospect list (seeded 2026-08-14, web search only — verify before sending)

Found via Google-dork-style web searches per "Where to find prospects" above. Names are
from public sources (Crunchbase/LinkedIn/The Org); **no email addresses were guessed**.
Verify company size + get email via LinkedIn or Hunter/Apollo before outreach.

### Tier A

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| Userlist | userlist.com/docs/legal/sub-processors/ | Email marketing for SaaS | Jane Portman (Co-Founder & CEO) | verified |
| SaasAnt | saasant.com/sub-processors/ | Accounting automation | Aravinth Chandrasekaran (Co-Founder & CEO) | verified |
| SalesQL | salesql.com/legal/subprocessors | LinkedIn email finder | Ariel Camino (CEO) | 11–50 employees, London |
| Ethnio | ethn.io/subprocessors | UX research recruiting | Nate Bolt (Founder) | verified |
| Unified.to | unified.to/gdpr | Unified API for HR/ATS/CRM | Roy Pereira / Alexey Adamsky (Co-Founders) | verified |
| Sessionboard | sessionboard.com/legal/list-of-sub-processors | Conference/event mgmt | Chris Carver (Co-Founder & CEO) | verified |
| OpenStatus | openstatus.dev | Open-source status pages | Thibault Le Ouay + Max | 2-person bootstrapped team — ideal fit |

### Tier B

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| Astra Security | help.getastra.com/articles/6386951398 | Security scanning | Shikhil Sharma (CEO) | funded, may be >50 employees |
| RescueTime | help.rescuetime.com/article/122 | Time tracking | Robby Macdonell (CEO) | |
| Trustmary | trustmary.com/list-of-subprocessors | Testimonial marketing | Johannes Karjula (CEO) | raised $2.2M, Finland |
| SmartSurvey | smartsurvey.com/company/sub-processors | Survey platform | Mo Naser (CEO) | $5.5M revenue, may be large |
| Uptime.com | uptime.com/subprocessors | Website/uptime monitoring | Michael Esposito (CEO) | ~28 employees, borderline size |
| ChatLab | chatlab.com/subprocessors | AI chatbot for support/sales | not found | Swiss (Kriens), unfunded, small — chatlab.com is NOT chatlabs.com (Michel Tjoeng, NY-based, different co); don't conflate |
| Lookback | help.lookback.io | User research | Henrik Mattsson (CEO) | resolved 2026-08-15 — current CEO per Crunchbase/Pillar VC; founders (Bengtsson/Littke) no longer run it |
| Opper AI | producthunt.com/products/opper-ai | AI gateway (EU) | Göran Sandahl (CEO & Co-Founder) | resolved 2026-08-15; VC-backed (Luminar/Emblem/Greens Capital), still early enough to be worth a shot |
| Formbricks | formbricks.com/about | Open-source survey/feedback platform | Johannes Dancker (Co-Founder & CEO) | seed stage, Kiel Germany, small team |
| Cloud-IAM | cloud-iam.com/gdpr-sub-processor | Keycloak-as-a-service | François-Guillaume Ribreau (Co-Founder & Co-CEO) | dev infra, small team |
| Hook0 | hook0.com/gdpr-subprocessors | Webhook infrastructure (EU-hosted) | David Sferruzza (Co-Founder & CTO) | resolved 2026-08-15 — co-founded with F-G Ribreau (same person as Cloud-IAM contact above); used the CTO here instead so the two companies aren't both pitched to Ribreau |

### New prospects (added 2026-08-15, web search + sub-processors.com/recent directory)

#### Tier A

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| Capgo | capgo.app/subprocessors/ | Live updates for Ionic/Capacitor mobile apps | Martin Donadieu (Founder) | ~6-person team, profitable/bootstrapped — great fit |
| Taloflow | taloflow.ai/subprocessors | AI software-vendor selection | Louis-Victor Jadavji (CEO & Co-Founder) | YC W21, 1–25 employees |
| Gruntwork | gruntwork.io/legal/data-subprocessor-list | DevOps/IaC infrastructure | Josh Padnick (CEO) | 18 employees, serves startups-to-enterprise B2B |
| AskYourTeam | askyourteam.com/legal/sub-processors-list | Employee experience platform | Chris O'Reilly (CEO & Co-Founder) | 11–50 employees, NZ |

#### Tier B

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| Amio | amio.io/sub-processors | Conversational AI for customer support | Matouš Kučera (CEO & Founder) | founded 2015, size unconfirmed |
| Fyr | fyr.ai/sub-processors/ | AI marketing/BI platform | Freddy Aurso (CEO) | Norway, size unconfirmed |

#### Needs more digging (found via sub-processors.com, not yet verified for size/decision-maker)

SFDevTools (sfdevtools.com/docs/subprocessors), Jetsend (jetsend.com/subprocessors/), Talis
(talis.com/legal/sub-processors/), SideDrawer (sidedrawer.com/legal/sub-processors), DocDigitizer
(docdigitizer.com/sub-processors/), CoSkip (coskip.com/subprocessors), Capcade
(capcade.com/list-of-subprocessors). Several other sub-processors.com listings were excluded as
already using a trust-center platform (trust.*/trustcenter.* subdomains — BalkanID, Oxolo,
Flower Labs, AskYourDatabase, Quantrium — disqualified by criterion #2) or clearly >50 employees
(Testim, Unstructured, Bunny, MangoApps, Deque, GoDaddy, Ivanti, Atlassian, SLB).

**New source for future Monday list-building:** sub-processors.com/recent lists newly-added
subprocessor pages across all company sizes — faster than one-off Google dorks, worth checking
weekly.

### Ready-to-send LinkedIn connect notes

Drafted from the template above, personalized per company, kept under LinkedIn's
~300-char connect-note limit. Copy, paste, send yourself — sending is your action, not
something to automate.

| Name | Company | Connect note |
|---|---|---|
| Jane Portman | Userlist | Hi Jane — saw Userlist's sub-processor page, rare for a team your size. I work on tooling in that exact space (vendor sub-processor monitoring), thought it'd be good to connect. |
| Aravinth Chandrasekaran | SaasAnt | Hi Aravinth — saw SaasAnt's sub-processor list, solid to have as a smaller team. I build tooling in that exact space, thought it'd be good to connect. |
| Ariel Camino | SalesQL | Hi Ariel — noticed SalesQL keeps a public sub-processor page, not common at your size. I work on tooling for tracking exactly those changes, thought it'd be good to connect. |
| Nate Bolt | Ethnio | Hi Nate — saw Ethnio's sub-processor page. I build tooling in that exact space (monitoring vendor sub-processor changes), thought it'd be good to connect. |
| Roy Pereira | Unified.to | Hi Roy — saw Unified's sub-processor disclosure, sharp for a dev-infra startup. I work on tooling for tracking exactly those changes, thought it'd be good to connect. |
| Chris Carver | Sessionboard | Hi Chris — saw Sessionboard's sub-processor list, rare for a team your size. I build tooling in that exact space, thought it'd be good to connect. |
| Thibault Le Ouay | OpenStatus | Hi Thibault — love what you and Max are building with OpenStatus. I work on tooling adjacent to that (vendor sub-processor monitoring), thought it'd be good to connect. |
| Shikhil Sharma | Astra Security | Hi Shikhil — saw Astra's sub-processor page. I build tooling for tracking vendor sub-processor changes — figured a security company would get the problem instantly. |
| Robby Macdonell | RescueTime | Hi Robby — saw RescueTime's sub-processor disclosure. I work on tooling in that exact space, thought it'd be good to connect. |
| Johannes Karjula | Trustmary | Hi Johannes — saw Trustmary's sub-processor list. I build tooling for tracking vendor sub-processor changes, thought it'd be good to connect. |
| Mo Naser | SmartSurvey | Hi Mo — saw SmartSurvey's sub-processor page. I work on tooling in that exact space, thought it'd be good to connect. |
| Michael Esposito | Uptime.com | Hi Michael — saw Uptime.com's sub-processor list. I build tooling adjacent to monitoring — tracking vendor sub-processor changes specifically — thought it'd be good to connect. |
| Johannes Dancker | Formbricks | Hi Johannes — saw Formbricks' sub-processor page, sharp for an early-stage team. I build tooling for tracking exactly those changes, thought it'd be good to connect. |
| François-Guillaume Ribreau | Cloud-IAM | Hi François — saw Cloud-IAM's GDPR sub-processor page. I build tooling in that exact space, thought it'd be good to connect. |
| Henrik Mattsson | Lookback | Hi Henrik — saw Lookback's sub-processor disclosure. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |
| Göran Sandahl | Opper AI | Hi Göran — congrats on Opper's launch as the EU AI gateway. I work on tooling adjacent to that (vendor sub-processor monitoring), thought it'd be good to connect. |
| David Sferruzza | Hook0 | Hi David — saw Hook0's GDPR sub-processor page, nice for a bootstrapped team. I build tooling in that exact space, thought it'd be good to connect. |
| Martin Donadieu | Capgo | Hi Martin — saw Capgo's sub-processor page, rare for a 6-person team. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |
| Louis-Victor Jadavji | Taloflow | Hi Louis-Victor — saw Taloflow's sub-processor list. I build tooling in that exact space (vendor change monitoring), thought it'd be good to connect. |
| Josh Padnick | Gruntwork | Hi Josh — saw Gruntwork's data sub-processor list. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |
| Chris O'Reilly | AskYourTeam | Hi Chris — saw AskYourTeam's sub-processor list. I work on tooling in that exact space, thought it'd be good to connect. |

No note drafted for ChatLab / SaaS Custom Domains — decision-maker name still unconfirmed,
find them on LinkedIn first (company page → People). Amio / Fyr (Tier B) also undrafted — verify
size/fit before spending a connect on them.

### Tier A email drafts (created 2026-08-15, sitting in Gmail Drafts — not sent)

Personalized per the Tier A template above, using emails found via web search (not guessed).
Review and send yourself:

| Name | Company | Email used | Note |
|---|---|---|---|
| Ariel Camino | SalesQL | ariel@salesql.com | direct, CEO |
| Nate Bolt | Ethnio | nate@ethn.io | direct, Founder |
| Chris Carver | Sessionboard | chris@sessionboard.com | direct, CEO |
| Thibault Le Ouay | OpenStatus | ping@openstatus.dev | general inbox, no direct address found |
| Aravinth Chandrasekaran | SaasAnt | support@saasant.com | general inbox, no direct address found |
| Jane Portman | Userlist | jane@uibreakfast.com | direct address, but published on her personal site (UI Breakfast), not userlist.com — flagged in the draft in case a userlist.com address is preferred |

**Roy Pereira (Unified.to) — still not drafted (2026-08-15 re-check):** no direct or generic
email found anywhere public; unified.to only offers a contact form and Discord support, and the
one email surfaced (hello@calendarhero.com) belongs to Roy's *previous* company, not Unified.to —
using it would misfire. Options: submit via unified.to/contact yourself, or find his personal
email via Hunter/Apollo/LinkedIn InMail.

### Unclear / needs more digging

- **SaaS Custom Domains** (saascustomdomains.com/legal/subprocessors) — very small/solo, no founder name found
- ~~Conduktor~~ — excluded, raised $52M, enterprise-scale now, not a fit

### Competitive/content signal (not prospects — observe only)

- **Registora** (registora.com) — "The Subprocessor Registry for B2B SaaS", adjacent concept
- **PageCrawl.io** — has a blog post on subprocessor monitoring, SEO-adjacent competitor signal

## KPIs (30 days)

| Stage | Target | Healthy rate |
|---|---|---|
| Prospects found | 400 (100/wk) | — |
| Emails sent | 300 | — |
| Open | 150+ | 50%+ (lower → subject/deliverability) |
| Reply | 20–30 | 7–10% (lower → message; high-but-negative → targeting) |
| Demo/call | 12–20 | ~60% of replies |
| Trial | 10–15 | ~70% of calls (no card = low friction) |
| **Paid** | **5–10** | 30–50% of trials (higher if trial catches a real change) |

**North-star metric: calls per week.** Everything else is derived.

## Feature exceptions this month (only two)

1. Cold-email domain setup (infrastructure, protects the product's email)
2. AI Questionnaire waitlist on landing (demand measurement = acquisition data, ~30 min)

Everything else: "Would talking to 20 more prospects create more value than building
this?" — Yes. Talk to prospects.

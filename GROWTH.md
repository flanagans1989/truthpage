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

Never send cold email from **usetrustpages.com** — if it gets flagged, magic links and
customer notifications die with it. Buy a secondary domain (e.g. gettrustpages.com),
set up SPF/DKIM, warm up 1–2 weeks, cap at 20–30/day.

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

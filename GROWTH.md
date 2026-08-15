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
| Unified.to | unified.to/gdpr | Unified API for HR/ATS/CRM | Roy Pereira / Alexey Adamsky (Co-Founders) | resolved 2026-08-15 — direct email found, see email drafts section |
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
| ChatLab | chatlab.com/subprocessors | AI chatbot for support/sales | Marcin Piotr Rabiej (Prezes Zarządu / President of the Board) | resolved 2026-08-15, see "Third pass" table below — Poland-registered (Kraków), not the Swiss/Kriens entity some aggregators index; also not chatlabs.com (Michel Tjoeng, NY, unrelated company) |
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
| Amio | amio.io/sub-processors | Conversational AI for customer support | Matouš Kučera (CEO & Founder) | resolved 2026-08-15 via his LinkedIn (still active CEO, ~€360k ARR / 100+ e-shops per his own recruiting post) — small team, good fit |
| Fyr | fyr.ai/sub-processors/ | AI marketing/BI platform | Freddy Aurso (CEO) | resolved 2026-08-15 — LinkedIn confirms 11–50 employees, Norway, right at the segment's size cap |

#### More resolved 2026-08-15 (moved out of "needs more digging")

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| DocDigitizer | docdigitizer.com/sub-processors/ | Document digitization/OCR | João Fernandes (Founder & CEO) | 15 employees, Lisbon — good fit |
| CoSkip | coskip.com/subprocessors | Voice-first AI for field service teams | Andrew M. Jensen (Founder & CEO) | 1–10 employees — great fit |
| SideDrawer | sidedrawer.com/legal/sub-processors | Digital vault for financial services | J. Gaston Siri (Co-Founder, CEO & CTO) | 27 employees, Toronto — Tier B (fintech-adjacent, borderline size) |
| SaaS Custom Domains | saascustomdomains.com/legal/subprocessors | Custom domains/white-labelling for SaaS | Drago Crnjac (Founder & CEO) | resolves the "no founder name found" gap from the original list; very small/solo |

#### Third pass 2026-08-15 (final — every open name/size question below is now closed)

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| ChatLab | chatlab.com/subprocessors | AI chatbot for support/sales | Marcin Piotr Rabiej (Prezes Zarządu / President of the Board) | resolved via Polish KRS company registry (rejestr.io) — the site's footer says "ChatLab Sp. z o.o., Kraków", **not** the Swiss/Kriens entity Tracxn had indexed under the same name; use this Poland-registered company |

**Excluded (confirmed too large / not independent):**
- **Capcade** — 52 employees, CEO identity conflicts across sources
- **Talis** (talis.com) — acquired by Kortext (a "global leader in digital content, library and
  learning solutions") from Sage on 2025-10-08; no longer an independent small company, exclude
- **Jetsend** (jetsend.com) — confirmed part of **Maropost**'s product portfolio, not an
  independent company; exclude

**Permanently unresolved:** SFDevTools — checked homepage, about page, and web search three
times; the team writes in first-person plural ("we built the tool we wished existed") with no
name anywhere public. Likely a genuinely anonymous solo project — skip rather than keep digging.

Several other sub-processors.com listings were excluded as already using a trust-center platform
(trust.*/trustcenter.* subdomains — BalkanID, Oxolo, Flower Labs, AskYourDatabase, Quantrium —
disqualified by criterion #2) or clearly >50 employees (Testim, Unstructured, Bunny, MangoApps,
Deque, GoDaddy, Ivanti, Atlassian, SLB).

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
| João Fernandes | DocDigitizer | Hi João — saw DocDigitizer's sub-processor page. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |
| Andrew Jensen | CoSkip | Hi Andrew — saw CoSkip's sub-processor page, rare for a small field-service AI team. I build tooling in that exact space, thought it'd be good to connect. |
| J. Gaston Siri | SideDrawer | Hi Gaston — saw SideDrawer's sub-processor list, sharp for a fintech-adjacent team. I build tooling in that exact space, thought it'd be good to connect. |
| Drago Crnjac | SaaS Custom Domains | Hi Drago — saw SaaS Custom Domains' sub-processor page, rare for a solo/small tool. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |
| Marcin Rabiej | ChatLab | Hi Marcin — saw ChatLab's sub-processor page. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |
| Matouš Kučera | Amio | Hi Matouš — saw Amio's sub-processor page. I build tooling in that exact space, thought it'd be good to connect. |
| Freddy Aurso | Fyr | Hi Freddy — saw Fyr's sub-processor page. I build tooling for tracking exactly those vendor changes, thought it'd be good to connect. |

Every prospect on the list now either has a connect note above or is explicitly excluded/dead-end
(see the "Third pass" and "Excluded" notes in the prospect tables) — nothing left unresolved as
of 2026-08-15. SFDevTools is the one deliberate skip (genuinely anonymous project, no name to
address).

**⚠️ LinkedIn free-tier hard limit discovered 2026-08-15:** personalized connection notes are
capped at **3 per calendar month** on a free account (LinkedIn shows the remaining count in the
"Davetinize not eklensin mi?" dialog). Connects without a note have no such cap. **Sent with a
note (used the 3-note quota for this month):**

| Name | Company |
|---|---|
| Matouš Kučera | Amio |
| Martin Donadieu | Capgo |
| Thibault Le Ouay | OpenStatus |

**Sent without a note 2026-08-15 (quota-free, rest of the list) — all pending acceptance:**

Jane Portman (Userlist), Aravinth Chandrasekaran (SaasAnt), Ariel Camino (SalesQL), Nate Bolt
(Ethnio), Roy Pereira (Unified.to), Chris Carver (Sessionboard), Shikhil Sharma (Astra Security),
Johannes Karjula (Trustmary), Mo Naser (SmartSurvey), Johannes Dancker (Formbricks),
François-Guillaume Ribreau (Cloud-IAM), Henrik Mattsson (Lookback), Göran Sandahl (Opper AI),
David Sferruzza (Hook0), Louis-Victor Jadavji (Taloflow), Josh Padnick (Gruntwork — on
sabbatical, may be slow to respond), Chris O'Reilly (AskYourTeam), João Fernandes (DocDigitizer),
Andrew Jensen (CoSkip), J. Gaston Siri (SideDrawer), Drago Crnjac (SaaS Custom Domains), Marcin
Rabiej (ChatLab), Freddy Aurso (Fyr) — **23 sent**.

**Skipped — identity could not be confirmed on LinkedIn, would have connected with the wrong
person:**
- **Robby Macdonell (RescueTime)** — only match found is a different Robby Macdonell (Product
  Designer/Cofounder at Clearbox Legal, immigration tech, Seattle) with zero mention of
  RescueTime. Real RescueTime CEO's LinkedIn not found.
- **Michael Esposito (Uptime.com)** — no matching profile in search results (only an unrelated
  Cloud Engineer and a small-business owner, neither connected to Uptime.com).

**All 26 connects across this list are now sent or accounted for** — 3 with a note, 23 without,
2 skipped for a documented reason. Nothing left to send from the original prospect list.

### Tier A email drafts (created 2026-08-15)

Personalized per the Tier A template above, using emails found via web search (not guessed).

**All 7 sent 2026-08-15** (reviewed and sent on request):

| Name | Company | Email used | Note |
|---|---|---|---|
| Ariel Camino | SalesQL | ariel@salesql.com | direct, CEO |
| Nate Bolt | Ethnio | nate@ethn.io | direct, Founder |
| Chris Carver | Sessionboard | chris@sessionboard.com | direct, CEO |
| Thibault Le Ouay | OpenStatus | ping@openstatus.dev | general inbox, no direct address found |
| Aravinth Chandrasekaran | SaasAnt | support@saasant.com | general inbox, no direct address found |
| Jane Portman | Userlist | jane@uibreakfast.com | direct address, published on her personal site (UI Breakfast), not userlist.com |
| Roy Pereira | Unified.to | roy@unified.to | direct, CEO |

**Next up:** wait for replies (track in the Fri metrics retro), and start sending the LinkedIn
connect notes above — that's still a manual step.

### Unclear / needs more digging

- ~~SaaS Custom Domains~~ — resolved 2026-08-15, see "More resolved" table above (Drago Crnjac)
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

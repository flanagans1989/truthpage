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
| RescueTime | help.rescuetime.com/article/122 | Time tracking | Robby Macdonell (CEO) | LinkedIn identity unconfirmed (2026-08-15) — only match found is a different person; no connect sent, see "Skipped" note below |
| Trustmary | trustmary.com/list-of-subprocessors | Testimonial marketing | Johannes Karjula (CEO) | raised $2.2M, Finland |
| SmartSurvey | smartsurvey.com/company/sub-processors | Survey platform | Mo Naser (CEO) | $5.5M revenue, may be large |
| Uptime.com | uptime.com/subprocessors | Website/uptime monitoring | Michael Esposito (CEO) | ~28 employees, borderline size; no matching LinkedIn profile found (2026-08-15) — no connect sent, see "Skipped" note below |
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

#### Fourth pass 2026-08-15 (re-checked sub-processors.com/recent, same page — still slow-moving)

| Company | Subprocessor page | Product | Decision-maker | Note |
|---|---|---|---|---|
| Syngency | syngency.com/gdpr/subprocessors/ | Software for modeling/talent agencies | Glen Ward (CEO) | 11 employees, LA — good fit |
| Cyfox | help.cyfox.com/en/articles/10131049-list-of-sub-processors | AI-driven XDR/security compliance | Yossi Tal (CEO) | 11–50 employees, funded — Tier B, security angle should land well |

**Excluded:** LeaveLogic — acquired by Unum Group in 2018, no longer an independent company.

### LinkedIn connect notes (sent 2026-08-15 — see quota/status section below)

Drafted from the template above, personalized per company, kept under LinkedIn's
~300-char connect-note limit. All were sent on 2026-08-15 (3 with the note text below, the
rest without a note due to the monthly cap — see "LinkedIn free-tier hard limit" below for
which is which).

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

**Sender correction (found 2026-08-31):** these 7 were sent from **deraksizolasyon@gmail.com**,
not studiominhagen@gmail.com as earlier notes claimed. Replies land in that inbox. This is also a
likely contributor to the 0% reply rate — a personal gmail carrying an unrelated insulation
business's name is weak sender identity for B2B cold email. Fixed going forward, see
"Sender identity" below.

**Next up:** wait for replies/accepts (track in the Fri metrics retro). Both the emails and the
LinkedIn connects from this batch are fully sent — nothing left to send from this list.

## Outreach status check + follow-ups (2026-08-31)

First status check since the 2026-08-15 send. Day+3/+7/+14 follow-ups had all been missed.

**Results of the 2026-08-15 batch (16 days in):**
- **Email: 7 sent, 0 replies, 0 bounces.** Only inbound was a SaasAnt support auto-ack ticket
  (##339815##). All 7 were delivered.
- **LinkedIn: 26 connects sent, 5 accepted (19%), 21 still pending.** Accepted: Marcin Rabiej
  (ChatLab, 21 Aug), Martin Donadieu (Capgo, 19 Aug), Göran Sandahl (Opper AI, 15 Aug), Drago
  Crnjac (SaaS Custom Domains, 15 Aug), Thibault Le Ouay (OpenStatus, 15 Aug).
- **Gap found:** of the 5 who accepted, only 2 (Martin, Thibault) had ever been messaged — and
  those 2 got no reply. Three warm, accepted connections sat untouched for two weeks.

**Sent 2026-08-31:**
- LinkedIn first DM to the 3 unmessaged accepted connections: Marcin (ChatLab), Göran (Opper AI),
  Drago (SaaS Custom Domains).
- LinkedIn single follow-up to Martin (Capgo) and Thibault (OpenStatus).
- Email thread follow-up ("close the loop" variant, offers a 3-month check-back) to 6 of the 7:
  Roy (Unified.to), Jane (Userlist), SaasAnt support, Chris (Sessionboard), Nate (Ethnio),
  Ariel (SalesQL).
- **OpenStatus email deliberately skipped** — Thibault got a LinkedIn follow-up the same day;
  a second channel on the same day would be over-contact.

## Sender identity: denizhan@usetrustpages.com (set up 2026-08-31)

Cold email was going out from a personal gmail. Fixed by putting outreach on the product domain,
free, using infrastructure already in place:

**Done (Cloudflare, deraksizolasyon@gmail.com account, zone usetrustpages.com):**
- Email Routing enabled. Destination address `studiominhagen@gmail.com` added and verified.
- Routing rule `denizhan@usetrustpages.com` → `studiominhagen@gmail.com`, Active. Catch-all left
  Disabled (drop) on purpose.
- DNS records added and locked: 3 MX (route1/2/3.mx.cloudflare.net), Cloudflare DKIM TXT
  (cf2024-1._domainkey), and root SPF `v=spf1 include:_spf.mx.cloudflare.net ~all`.
- **Inbound verified end to end** — test mail to denizhan@usetrustpages.com landed in
  studiominhagen's inbox within a minute.
- No conflict with Resend: Resend sends from the `send.usetrustpages.com` subdomain and has its
  own MX/SPF there, untouched. Root had no MX before this.

**Left to the user (credential entry is out of scope for Claude):** Gmail → Settings → Accounts →
"Send mail as" → add `denizhan@usetrustpages.com` (name: Denizhan Koçakgöl, uncheck "Treat as
alias"), SMTP host `smtp.resend.com`, port 587 TLS, username `resend`, password = a Resend API
key. The confirmation code arrives at studiominhagen via the routing above.

**Known follow-up:** the root SPF only authorizes Cloudflare. Mail sent through Resend SMTP with a
`@usetrustpages.com` From will fail SPF but pass DKIM (resend._domainkey covers the root domain),
and DMARC is `p=none`, so it still delivers. Worth adding `include:amazonses.com` to the root SPF
record for full alignment.

**Mailbox consolidation decision:** TrustPages identity now centers on studiominhagen@gmail.com
(LinkedIn + Paddle already there, plus denizhan@usetrustpages.com routing). Existing email threads
from the 2026-08-15 batch stay on deraksizolasyon@gmail.com, since replies would go there.

### Unclear / needs more digging

- ~~SaaS Custom Domains~~ — resolved 2026-08-15, see "More resolved" table above (Drago Crnjac)
- ~~Conduktor~~ — excluded, raised $52M, enterprise-scale now, not a fit

## New prospect batch (2026-08-16, Round 1 + Round 2 — not yet contacted)

Fresh discovery pass, disjoint from every company above. Round 1 used Google dorks +
sub-processors.com directory + niche-vertical search (~40 queries). Round 2 aimed for
8-15 more but hit the session's WebSearch quota cap (200/200) very early and had to fall
back to guessed-URL WebFetch, which yielded far fewer verifiable leads — only 1 new
company survived full verification. **Round 3 (resume broader discovery once quota resets)
is still open** — see "Next up" below.

### Round 1 — 6 verified (quality bar met)

| Company | Website | Subprocessor page | Type | Employees | B2B evidence | Trust-center | Recent activity | Contact | LinkedIn | Email | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Swantide | swantide.com | swantide.com/subprocessors | Static HTML | ~12 | AI agents for Salesforce ops, sold to B2B RevOps/IT | None | Page updated Jul 2026 | Taylor Lint (Founder & CEO) | linkedin.com/in/taylorelizabethlint | not found | A |
| Cometly | cometly.com | cometly.com/sub-processors | Static HTML | 6-11 | Marketing attribution for B2B SaaS | None | Page updated Aug 2026 | Matt Pattoli (Co-founder, DPO) | linkedin.com/in/mattpattoli | privacy@cometly.com — role-based/DPO alias, not a clean personal address | A |
| Botdoc | botdoc.io | botdoc.io/botdoc-subprocessors/ | Static HTML | 16-19 | Secure doc/ID transport for dealerships/lenders | None | May 2026 Trust Stamp partnership | Karl Falk (Founder & CEO) | linkedin.com/in/karlfalk | not found | A |
| Hunter.io | hunter.io | hunter.io/subprocessors | Static HTML | 36-38 | Email-finding SaaS, customers incl. Google/IBM/Microsoft | None (own page, not managed) | Active 2026 changelog | Matthew Tharp (CEO) | linkedin.com/in/matttharp | **matt@hunter.io — direct, verified** | A |
| GaggleAMP | gaggleamp.com | gaggleamp.com/subprocessors | Static HTML | 22-28 | Employee advocacy platform for B2B brands | None | Jun 2026 UI refresh (Capterra) | Glenn Gaudet (Founder & CEO) | linkedin.com/in/glenng | not found | A |
| Zapiet | zapiet.com | Intercom article (support.zapiet.com/.../zapiet-s-subprocessors) | Static/Intercom | 22 | Shopify pickup/delivery app, sold to merchants (not enterprise-buyer profile) | None | May 2026 blog/changelog | Andrew Cargill (Founder & CEO) | linkedin.com/in/cargi | not found | B |

**Round 1 excluded (do not re-research):** Chameleon, Knak, Knit (goknit.com), ZeroBounce, Oliv AI
— all use SafeBase/Vanta/Drata/Sprinto trust centers. Composio, Maxio, Julius AI, Twingate, Vendr,
Lokalise — managed trust center and/or too large. Scratchpad, GrowthX AI, Spekit, Zeplin, Reprise,
Timely, Sylvera, Binary Defense, Lob, Paragon, Sona/getsona.com, Suzy, BigTime Software, Digistorm,
Aloware — 50+ employees. Featurebase — ~3 employees, too small. CheckThat.ai — good page but
employee count/founder unverifiable. ProValet, WP Hercules — SMB buyer, not enterprise/security
profile. Gleam.io, Fathom Analytics — subprocessor page stale (2021/2022). Yesware — absorbed into
Vendasta, not independent.

### Round 2 — 1 new verified (WebSearch quota cut the pass short)

| Company | Website | Subprocessor page | Type | Employees | B2B evidence | Trust-center | Recent activity | Contact | LinkedIn | Email | Tier |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Loops | loops.so | tryloops.notion.site/tryloops/Loops-Subprocessor-List-f391cb8ee6f841a7aa7db9a1c14b3037 | Notion | ~12 | Email platform for B2B SaaS, YC W22 | None detected | 2026: shipped Claude Code/Cursor/Codex integrations, PH 4.9/132 | Chris Frantz (Co-founder) | personal LinkedIn unconfirmed (only company page + X @frantzfries) | not found (only an obfuscated site contact) | A (LinkedIn-ready once personal LinkedIn confirmed) |

**Round 2 excluded (do not re-research):** Orbiit.ai (acquired by Hivebrite, now 143 employees),
Gatheround (acquired by Donut, no current contact verifiable), Cap Orbit (2-10 employees, no
founder name found), Aleph/getaleph.com (105 employees), ZenML (trust-center status ambiguous,
excluded out of caution), June.so (team absorbed into Amplitude Aug 2025, page stale since Jul
2023), Loom Analytics/Claudio (subprocessor names only in a downloadable Word doc — unmonitorable;
2-10 employees), Moesif (WSO2 subsidiary, no verifiable personal contact), Wiza.co (LinkedIn name
collision with an unrelated Zimbabwean company), Depot.dev (employee count unverifiable, only
generic help@ found), Data Zoo (trust.datazoo.com reads as a managed trust-center domain).
pganalyze, MaestroQA, Common Room, Granola, AirOps, Baseten — no subprocessor page found at
guessed URLs (undiscoverable this session, not confirmed excluded).

### Combined shortlists (Round 1 + Round 2, Tier A only, Zapiet excluded as Tier B)

**A) EMAIL-READY** (verified direct personal email, not a generic/role inbox):

| Company | Contact | Direct email | Subprocessor page |
|---|---|---|---|
| Hunter.io | Matthew Tharp, CEO | matt@hunter.io | hunter.io/subprocessors |

**B) LINKEDIN-READY** (strong fit, no verified direct email):

| Company | Contact | LinkedIn | Subprocessor page |
|---|---|---|---|
| Swantide | Taylor Lint, CEO | linkedin.com/in/taylorelizabethlint | swantide.com/subprocessors |
| Cometly | Matt Pattoli, Co-founder/DPO | linkedin.com/in/mattpattoli | cometly.com/sub-processors — only email found is role-based (privacy@), treated as no-direct-email |
| Botdoc | Karl Falk, CEO | linkedin.com/in/karlfalk | botdoc.io/botdoc-subprocessors/ |
| GaggleAMP | Glenn Gaudet, CEO | linkedin.com/in/glenng | gaggleamp.com/subprocessors |
| Loops | Chris Frantz, Co-founder | personal LinkedIn URL needs confirming before outreach (company page: linkedin.com/company/sendwithloops) | tryloops.notion.site/... |

**Next up (2026-08-16):** Prospect research paused here per user decision — priority moved to
GitHub Actions/Claude Code infra setup. Nothing from this batch has been contacted yet. When
resumed: (1) optionally run Round 3 once the session WebSearch quota resets, target still 12-15
total; (2) confirm Chris Frantz's personal LinkedIn URL before contacting Loops; (3) start
outreach with the EMAIL-READY row (Hunter.io) and the 4 confirmed LINKEDIN-READY rows.

**Update 2026-08-31 — still uncontacted, deliberately held:**
- **Hunter.io (matt@hunter.io)** — email was drafted and then held back rather than sent from the
  personal gmail. Send it once `denizhan@usetrustpages.com` send-as is live (see "Sender identity"
  above). New prospect, first impression matters.
- **The 4 LinkedIn-ready rows** (Swantide/Taylor Lint, Cometly/Matt Pattoli, Botdoc/Karl Falk,
  GaggleAMP/Glenn Gaudet) — held for **2026-09-01**, when the free-tier personalized-note quota
  resets (3/month; August's was spent on 2026-08-15). Plan: notes for the 3 strongest, the 4th
  without a note. User chose this over sending all 4 note-less on 08-31.
- Loops/Chris Frantz still needs his personal LinkedIn URL confirmed before any contact.

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

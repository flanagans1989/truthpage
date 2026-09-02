# Launch assets

Copy-paste-ready copy for Product Hunt, Show HN and Reddit. Written once so a
launch day is "paste and adjust the date," not "write three posts under
pressure." Update the bracketed placeholders (`[DATE]`, `[YOUR NAME]`) before
posting — nothing else needs editing to be true on the day you use it.

Every claim in here is checked against what actually ships today: 3-tier
pricing (Free / Starter $29 / Growth $89), Gemini 2.5 Flash classification,
the SHA-256-anchored downloadable audit ZIP (Growth only), the public vendor
directory, and the 14-day trial. Don't add a feature to the copy that isn't
live — a comment thread full of "actually it doesn't do that" is worse than
a smaller, accurate launch.

No competitor is named anywhere below, on purpose — same reasoning as
`/compare` on the site itself (`app/core/comparisons.py`): naming a rival our
own size on a launch post advertises them to an audience that hadn't heard
of them.

---

## Product Hunt

**Tagline** (60 chars max):
> Sub-processor compliance with cryptographic proof, automated

**Gallery order** (screenshots to prepare beforehand):
1. The public trust page (`/trust/trustpages`) — what a customer sees.
2. The approval queue with a side-by-side diff.
3. The evidence record page showing the SHA-256 anchor box.
4. `/pricing` — the three tiers.

**Description** (the block under the gallery):
> TrustPages watches your vendors' sub-processor pages so you don't have to
> check them by hand. Every change gets classified material or cosmetic by
> Gemini 2.5 Flash — cosmetic edits (a typo, a moved heading) publish
> themselves, anything that could affect your customers waits in an approval
> queue with a side-by-side diff.
>
> The part most tools stop at: a screenshot. TrustPages instead stores the
> vendor's raw HTML itself, fingerprinted with an independent SHA-256 hash
> and a timestamp, bundled into a downloadable ZIP with the diff and your
> decision trail — something an auditor can verify without trusting our
> dashboard at all.
>
> Free for 3 vendors, permanently, no card. Built by a solo developer who
> got tired of manually re-checking Stripe's sub-processor page every month.

**First comment** (post immediately after launch, from the maker account —
this is what actually drives PH engagement, not the listing itself):
> Hey — maker here. I built this because I kept a spreadsheet of vendor
> sub-processor pages I was supposed to re-check "sometime this month," and
> never did. The trigger was realizing our own DPA promises customers a
> heads-up under GDPR Article 28(2) when a sub-processor changes — a
> promise that's only as good as someone actually noticing the change.
>
> The technical bit I'm most proud of: every detected change stores the raw
> HTML before and after, hashed with SHA-256, so the evidence you hand an
> auditor isn't "trust our dashboard," it's a file they can verify
> themselves. Happy to answer anything about the scraping/classification
> pipeline, the pricing, or what's still missing (custom domains and
> Slack/webhook alerts are next).
>
> Free plan is 3 vendors forever, no card required, if you want to see your
> own trust page in the next two minutes: [LINK]

**Anticipated questions, answered in advance** (paste into replies, don't
wait to be asked if the thread is slow):
- *"How is this different from just watching the page with [generic
  monitoring tool]?"* — Most page-watchers give you a diff and a notification.
  TrustPages classifies the diff (so footer/menu noise never reaches you),
  keeps a dated document per change rather than just the current state, and
  the Growth plan adds a downloadable, hash-verified evidence pack — the
  file an auditor actually asks for, not a screenshot.
- *"Can it read pages that need JavaScript to render?"* — Yes, every plan
  (Free included) escalates to a real headless browser automatically when a
  page is behind bot protection or client-rendered; no configuration needed.
  Growth just gets a bigger daily budget for how often that can happen.
- *"Is my data monitored, or am I setting this up to protect myself?"* —
  Both directions: you add the vendors you use (nobody publishes on your
  behalf), and separately there's a public directory of already-verified
  vendor pages you can browse without an account.

---

## Show HN

**Title options** (HN strips marketing language fast — pick the plainest one):
1. `Show HN: I watch my vendors' sub-processor pages so I don't have to`
2. `Show HN: TrustPages – SHA-256-verified sub-processor change monitoring`
3. `Show HN: A GDPR Article 28(2) notice, drafted from the diff itself`

Prefer #1 for the front page (personal, low-hype); #2 if the audience
skews more compliance/security than general HN.

**Post body:**
> I got tired of manually re-checking whether Stripe, AWS etc. had quietly
> added a new sub-processor, so I built a small scraper + classifier that
> does it daily.
>
> How it works: fetch each vendor's sub-processor page (httpx first, a
> headless browser only if that gets blocked), normalize and hash the text,
> diff against the last version, and hand the diff to Gemini 2.5 Flash to
> classify as material or cosmetic. Cosmetic edits (typo fixes, reordered
> rows) auto-publish; anything that could actually matter — a new
> sub-processor, a new processing country — sits in a queue with a
> side-by-side diff until a human approves it.
>
> The part I spent the most time on: the evidence trail. Each change stores
> the vendor's raw HTML before and after, each independently hashed with
> SHA-256, plus the diff and who approved it — packaged as a downloadable
> ZIP so the "proof" isn't a claim about my dashboard, it's a file with a
> checksum anyone can verify.
>
> Stack: FastAPI + async SQLAlchemy on Postgres (Neon), Jinja2/HTMX for the
> UI (no frontend framework), APScheduler for the sweep, Gemini for
> classification, deployed on Render. Free tier is 3 vendors forever, no
> card. Code isn't open source (yet — still deciding), but happy to answer
> anything about the architecture, the scraping tiering, or the SSRF
> handling for a tool that fetches arbitrary user-supplied URLs.
>
> [LINK]

**HN-specific etiquette notes:**
- Don't reply to every comment — reply to the technical ones, let low-effort
  criticism sit unless it's factually wrong.
- If asked "why not open source" and the honest answer is "haven't decided,"
  say that — HN detects a rehearsed non-answer immediately.
- Post between 8–10am US Eastern on a weekday for the best chance at the
  front page; avoid Fridays and weekends.

---

## Reddit

Reddit punishes anything that reads like an ad far harder than PH or HN — the
post has to be useful on its own even to someone who never clicks through.
Lead with the problem or the technical detail, not the product name.

### r/SaaS

**Title:** `Built a tool that monitors vendor sub-processor pages after realizing our own compliance notice was only as good as someone remembering to check`

**Body:**
> Context: our DPA (like most B2B SaaS DPAs) promises customers a heads-up
> under GDPR Article 28(2) if we add or replace a sub-processor. In
> practice, "we'll notify you" depended on someone remembering to
> periodically re-read every vendor's sub-processor page by hand. Nobody
> did, reliably.
>
> Ended up building a small scraper that checks each vendor's page daily,
> diffs it, and uses an LLM to tell a real change (new sub-processor added)
> from noise (a typo fix, a reformatted table) — so only the changes that
> actually matter show up for review.
>
> Turned it into a small SaaS since a few other founders I talked to had the
> same spreadsheet-of-shame problem. Free for 3 vendors if anyone wants to
> try it on their own stack: [LINK]. Mostly posting because I think the
> "classify before you notify" approach is generally useful for anyone
> doing vendor-change monitoring, not just this specific tool.

### r/privacy or r/gdpr

**Title:** `A practical read on the GDPR Art. 28(2) sub-processor notice obligation — the part that's easy to miss`

**Body:**
> Something that comes up less than it should in GDPR compliance
> discussions: Article 28(2) requires a processor to give customers a
> chance to object before adding or replacing a sub-processor — but the
> actual mechanism most vendors use is just quietly updating a page on
> their site. There's no push notification standard for this. If nobody on
> your side is watching that page, your objection window closes without you
> knowing it opened.
>
> I ended up writing a tool to solve this for my own company (watches
> vendor pages, classifies changes, drafts the notice) — [LINK] if useful —
> but even without using any tool, the practical takeaway is worth
> spreading: if your vendor list is more than a couple of names, "I'll
> check periodically" is not a real compliance process. Either someone owns
> a calendar reminder for every single vendor, or something automated does.

### r/webdev (technical-audience angle, not the compliance angle)

**Title:** `The scraping/verification pipeline behind a "prove this page didn't change" tool`

**Body:**
> Sharing the technical approach behind a small tool I built, since the
> "how do you make scraped evidence actually trustworthy" problem might be
> useful outside my specific use case (GDPR sub-processor monitoring).
>
> Pipeline: httpx fetch first (fast, cheap), escalate to a real headless
> browser only when a page is client-rendered or bot-walled (detected by
> response signatures, not guessed upfront). Normalize the HTML to strip
> nav/cookie-banner/script noise, hash the normalized text for cheap
> re-check-did-anything-change, but *separately* hash the raw HTML too and
> store both — the normalized hash is for detecting change, the raw-HTML
> hash is what actually goes in front of an auditor, since normalization is
> a step they can't independently reproduce.
>
> Bundled per-change into a downloadable ZIP: before/after raw HTML,
> before/after normalized text, unified diff, and a plaintext manifest with
> both hashes and a timestamp. The idea is that "trust me, I have a
> dashboard" is a weaker claim than "here's a file, check the hash
> yourself."
>
> Product is [LINK] if the specific use case is relevant to you; otherwise
> happy to go deeper on the tiered-fetch or hashing approach in comments.

---

## Timing checklist (fill in before the actual day)

- [ ] Product Hunt scheduled for [DATE], maker comment drafted and ready to
      paste within the first 5 minutes of going live.
- [ ] Show HN posted same morning, 8–10am US Eastern.
- [ ] Reddit posts staggered across the day, not all at once — one
      subreddit at a time, reading the room before the next.
- [ ] `/vendors` directory has at least a dozen verified entries before
      launch — an empty-looking directory undercuts the "we actually
      monitor things" pitch.
- [ ] Confirm `/tools/audit-grader` and the sample evidence ZIP download
      both work end-to-end the morning of launch — these are what a
      skeptical HN/PH commenter will actually click.

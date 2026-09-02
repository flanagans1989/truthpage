# Audit evidence manifest — schema v2

`manifest.txt` is the one file in an audit evidence ZIP meant to be *read*,
not diffed against or parsed by a specific app version forever. This
document freezes its shape before PR 3 (RFC 3161 timestamping) and PR 4
(delivery log + objection window) both need to write into it — the format
is fixed here so those two PRs fill in fields rather than each inventing
their own half of the layout.

Implemented by `app/services/evidence.py` (`_render_manifest_v2`,
`parse_manifest_v2`, `detect_manifest_version`). If code and this document
ever disagree, this document is the spec and the code has a bug.

> **This schema may change until its first production deploy.** Once
> deployed, no field name, order, or value may change — a change after that
> point requires a new version number (v3), never a silent edit of v2. Two
> corrections were made to this exact section before any deploy happened
> (see the changelog at the bottom); that window is now closed once this
> reaches production.

## KURAL 0 — no backdated timestamping, ever, under any condition

No existing snapshot may EVER, under any circumstance, receive a
timestamp generated after the fact. A token obtained today attached to
HTML captured three months ago would be a document asserting an event
happened at a time it did not — the single failure mode that would
invalidate every legal claim this whole feature makes, for every pack,
retroactively.

Concretely:

- Every `change_event` row that existed before RFC 3161 support shipped is
  migrated to `timestamp_status = 'not_available_pre_tsa'` — a status the
  system may only ever assign at migration time or when there is
  genuinely no digest to stamp (see `app/services/tsa_retry.py`'s
  `new_raw_html_hash is None` branch), never chosen to "fix" a stuck
  record.
- `not_available_pre_tsa` is TERMINAL. No code path — not a retry pass,
  not a manual action, not a future migration — may ever move a row out
  of it. `stamp_change_event()` raises `BackdatedTimestampError` the
  instant it's called on one; this is enforced in code, not left as a
  status a caller could accidentally overwrite.
- New rows are set to `pending` explicitly at insert time (in
  `app/services/monitoring.py`, the moment a real change is detected and
  stored) — never relied on as a default. The column's own
  `server_default`/ORM default is deliberately `not_available_pre_tsa`,
  the safe, inert state: code that forgets to set it explicitly fails
  toward "no timestamp attempted" rather than toward a false claim.
- Verified by a trip-wire test
  (`tests/test_tsa_retry.py::TestKural0TripWire`), not just documented:
  calling the stamping function on a `not_available_pre_tsa` record must
  raise, and the retry pass's query must never select one in the first
  place.

## Rules

- **Always English.** `manifest.txt` is generated in English regardless of
  the tenant's UI language (de/fr/es). The evidence pack is read by an
  auditor or opposing counsel, not by whoever happened to configure the
  dashboard — one canonical language, always.
- **All timestamps are UTC, ISO 8601, with a trailing `Z`** (e.g.
  `2026-09-02T11:59:00Z`). Never local time, never a locale-formatted date.
- **Every field in the schema below is present in every pack.** A value
  TrustPages cannot supply today is written as `not_available` — literally
  that string, not blank, not omitted, and never guessed at or derived by
  approximation. A field genuinely absent is more honest than one estimated.
- **Generation is deterministic.** The same event, run through the
  generator twice, produces byte-identical `manifest.txt` output — no random
  ordering, no timestamp created from `now()` beyond `generated_at` itself,
  no locale-dependent formatting. The whole point is that this file gets
  hashed; two hashes for "the same" evidence would be a bug.
- **No legal conclusions.** This document records observed facts and
  cryptographic digests. It never asserts compliance, validity, or
  approval of anything. The words below may never appear anywhere in a
  generated manifest (case-insensitive) — enforced by
  `_assert_no_forbidden_terms` at generation time, not just by test:

  ```
  compliant, uyumlu, approved, onaylandı, valid consent,
  gdpr compliant, meets article 28
  ```

  **Resolved before any deploy:** an earlier draft of this schema had
  `review_action` take the value `approved_for_notification`, which
  collided with this exact list ("approved"). The fix was the value, not
  the rule — `review_action`'s permitted values are now
  `notice_released_by_reviewer` and `auto_published_cosmetic` (see
  `[REVIEW]` below): the system records the observed action only
  ("released" — a human let a drafted notice go out), never a legal
  characterization ("approved") of it. No exception to the forbidden-terms
  check was added; `validate_review_action` enforces this the same way
  `validate_objection_status` enforces the four permitted objection
  statuses below.
- **`[OBJECTION WINDOW]`'s `objection_status` may only take one of four
  exact forms** (`validate_objection_status` raises `ValueError` for
  anything else):
  - `Window open (closes <UTC>)`
  - `No objection recorded via TrustPages as of <UTC>`
  - `<N> objection(s) recorded`
  - `not_available`

  No other phrasing — nothing implying a conclusion ("cleared",
  "resolved", "compliant") is a permitted value.
- **The `#` comments below (`# MATERIAL | COSMETIC | UNCERTAIN`, `# PR 3
  dolduracak`, etc.) are documentation for this spec file only.** They are
  never written into a real `manifest.txt` — a legal-evidence document has
  no business containing implementation notes about which PR fills in
  which field.

## Schema

```
TrustPages Audit Evidence Pack
manifest_version: 2
generated_at: <UTC>
generator: TrustPages <app_version>

[NOTICE]
This pack records observed facts and cryptographic digests. It is not a
legal opinion and does not assert compliance with any regulation.

[SUBJECT]
tenant_name:
trust_page_url:
subprocessor_name:
source_url:
change_id:

[DETECTION]
detected_at:
previous_snapshot_captured_at:
current_snapshot_captured_at:
classification:                 # MATERIAL | COSMETIC | UNCERTAIN
classifier_model:                # e.g. gemini-2.5-flash
classifier_note: Automated assessment. Not a legal determination.

[EVIDENCE]
hash_algorithm: SHA-256
before_html_file:
before_sha256:
after_html_file:
after_sha256:
before_text_file:
before_text_sha256:
after_text_file:
after_text_sha256:
diff_file:
diff_sha256:

[TIMESTAMP]                      # filled by PR 3
timestamp_status:                # pending | retrying | timestamped | failed | not_available_pre_tsa
tsa_token_file:
tsa_authority_url:
tsa_time_utc:
tsa_chain_file:
verification_instructions: See README.txt — run ./verify.sh offline.

[REVIEW]
reviewed_by_name:
reviewed_by_email:
reviewed_at:
review_action:                   # notice_released_by_reviewer | auto_published_cosmetic

[NOTIFICATION]
notice_frozen_at:
notice_file:
sent_at:
recipient_count:
delivered_count:
bounced_count:
delivery_log_file:               # delivery_log.csv (redacted) or delivery_log_full.csv

[OBJECTION WINDOW]
window_days:
window_source:                   # e.g. "tenant configuration (default 30)"
window_opened_at:
window_closes_at:
objection_status:                # one of the four permitted forms — see Rules

[PACK CONTENTS]
<filename>  <sha256>             # every file in the ZIP, alphabetically
                                  # (case-insensitive), manifest.txt itself
                                  # excluded (see below)
```

## Field notes

`[SUBJECT]`, `[DETECTION]`, `[EVIDENCE]`, `[PACK CONTENTS]` (PR 2),
`[TIMESTAMP]` (PR 3), and now `[REVIEW]`/`[NOTIFICATION]`/`[OBJECTION
WINDOW]` (PR 4) are all populated from real data — every field this schema
lists is real or `not_available`, never a placeholder waiting on a future
PR.

A few fields worth calling out:

- **`previous_snapshot_captured_at`** is `not_available` even for a fresh
  event today: the pipeline only records the *moment a change was
  detected* (`ChangeEvent.created_at`), not a separately-stored "the prior
  snapshot was captured at time X". Adding that would be new data
  collection, out of scope for a format-only PR.
- **`current_snapshot_captured_at`** reuses `detected_at` — in the current
  pipeline, detection and current-snapshot-capture are the same instant.
- **`before_text_file`/`before_text_sha256`/`after_text_file`/`after_text_sha256`**
  are symmetric with the HTML pair — `before.txt`/`after.txt` are real
  files in the ZIP (the normalized text used for the diff), and every file
  named in `[PACK CONTENTS]` needs a field here saying what it is. (An
  earlier draft of this schema had one combined `raw_text_file` field
  pointing only at `after.txt`, leaving `before.txt` in the pack with no
  schema counterpart — fixed before any deploy, since a file an auditor
  can't identify from the manifest defeats the point of it.)
  Both are populated with real values today (not `not_available`) — the
  normalized text already exists on every event.
- **`before_sha256` / `after_sha256`** read the digest TrustPages computed
  at capture time (`Subprocessor.last_raw_html_hash` /
  `ChangeEvent.old_raw_html_hash` / `new_raw_html_hash`), not a hash
  recomputed from the ZIP's `before.html`/`after.html` at generation time.
  In the normal case (the capture was real) these are identical — same
  bytes, same SHA-256-over-UTF-8 algorithm as everywhere else in this
  document — because the stored hash was itself computed the same way over
  the same content. They diverge on purpose only when a capture is
  missing: `[EVIDENCE]` correctly reports `not_available`, while
  `[PACK CONTENTS]` still hashes whatever placeholder text
  ("Not captured for this change.") is physically sitting in the ZIP file
  of that name — `[PACK CONTENTS]` describes what's literally in the pack,
  `[EVIDENCE]` describes whether real evidentiary data exists.
- **`classifier_model`** reads the current Gemini model constant
  (`app.core.llm.analyzer._MODEL`) at generation time. This is not stored
  per-event — a future model change would report the *current* model for
  all past events' packs, not the model actually used on each one. Storing
  it per-event is a data-collection change outside this PR's scope, noted
  here rather than silently done.

## RFC 3161 timestamping

### What gets sent to the TSA

Only the SHA-256 digest of `after.html` (`ChangeEvent.new_raw_html_hash`)
— never the page content. RFC 3161 is designed exactly for this: the
timestamp authority attests "this digest existed at this time" without
ever seeing what it's a digest of. The TSA never learns which vendor page
a tenant monitors, what it says, or that TrustPages exists as their
customer. This is worth saying in the sales copy, not just here — see
`README.txt`'s wording in every pack.

### When a timestamp is requested

Only when a real change is detected and a new `change_event` row is
stored — never on a daily scan that finds nothing different. A "no
change" tick costs zero TSA calls; the retry pass only ever looks at rows
that already exist with `pending`/`retrying` status
(`app/services/tsa_retry.py::run_timestamp_retry_pass`).

### State machine

```
        (change_event created, new_raw_html_hash present)
                          │
                          ▼
                      pending ──────────────┐
                          │                 │
                (attempt, TSA fails)   (attempt, TSA succeeds)
                          │                 │
                          ▼                 ▼
                      retrying ──────► timestamped
                          │
             (attempt N == TSA_MAX_ATTEMPTS)
                          │
                          ▼
                       failed ──(manual retry)──► retrying
```

`not_available_pre_tsa` is not on this diagram — it is reachable only from
outside it (migration backfill, or a `new_raw_html_hash is None` event),
and nothing on this diagram ever points to it. `failed` is not terminal:
a person can manually retry from the dashboard, which resets the attempt
counter and returns the row to `retrying` for the next sweep tick.

The retry pass runs asynchronously at the very start of every existing
sweep cycle (`app/scheduler/jobs.py::run_sweep_cycle`) — not a new
worker/queue/broker. A TSA outage can never block, slow down, or fail the
scraping pass that runs after it in the same cycle; the two are
independent steps in the same tick.

### Configuration

```
TSA_PRIMARY_URL=https://freetsa.org/tsr   # default
TSA_FALLBACK_URL=                          # blank = no fallback attempted
TSA_TIMEOUT_SECONDS=20
TSA_MAX_ATTEMPTS=5
```

Only FreeTSA is configured today. `TSA_FALLBACK_URL` exists in the code
and is tried automatically whenever it's set (primary first, then
fallback), but shipping a second provider means also bundling its CA
chain (see below) — setting the URL without the chain would make a
fallback-issued token unverifiable by both `verify.sh` and `/verify`. Do
not set it without adding that file.

### Where the bundled CA chain comes from

`app/static_data/tsa/freetsa-chain.pem` — FreeTSA's root CA certificate
concatenated with their TSA signing certificate, fetched directly from
`https://freetsa.org/files/cacert.pem` and `https://freetsa.org/files/tsa.crt`
(FreeTSA's own published files, not a third-party mirror). Checked into
the repo rather than fetched at request time, so:

- a ZIP is buildable and `/verify` is checkable even if freetsa.org is
  down;
- the exact bytes trusted by `verify.sh` (shipped in every pack) and by
  the server-side `/verify` endpoint are identical and reviewable in this
  repo, not fetched live from a URL that could change.

**This is the only CA chain `/verify` and every `verify.sh` will ever
trust.** A pack's own `tsa-chain.pem` — inside an uploaded ZIP, or one an
attacker crafts to sit next to a forged token — is never read for trust
purposes. If it were, anyone could bundle a self-signed throwaway CA next
to a self-signed "token" and have their own upload "verify" against
itself; the whole feature would prove nothing.

## Delivery record and objection window (PR 4)

### KURAL 0 for this PR — released evidence is immutable

The moment a notice is released, these freeze and never change again:
the sent notice text (`ChangeEvent.notice_frozen_subject`/
`notice_frozen_body`, a separate copy from the editable `notice_subject`/
`notice_body` a tenant can still redraft for their own reference), the
reviewer's name/email/timestamp, the recipient-list size at send time
(`recipient_count`), and the objection window's length and close date
(`window_days`/`window_closes_at`). Enforced in code, not just documented:
`app/db/models/change_event.py`'s `@validates` guard raises
`FrozenNotificationFieldError` the instant anything tries to overwrite one
of these fields with a different value (`tests/test_frozen_notification_fields.py`).
The append-only delivery-event log (`notification_delivery_events`) is the
same idea applied to a whole table: rows are inserted, never updated.

### Reviewer identity ([REVIEW])

`reviewed_by_name`/`reviewed_by_email` are copied at the moment a human
approves a material change and releases its notice — never a live join to
the tenant's account, since a later rename or email change on that account
must not rewrite what already happened. A cosmetic change auto-published
by the classifier has no reviewer: `reviewed_by_name`/`_email`/`_at` stay
`not_available` and `review_action` reads `auto_published_cosmetic` —
never a placeholder name like `"system"`.

Approving a material change (`app/services/approval.py::approve_change_event`)
drafts the Article 28(2) notice if one doesn't already exist, freezes a
placeholder-resolved copy of it (`[OBJECTION WINDOW]` → the tenant's actual
window length, `[CONTACT]` → the tenant's own email — the only two
placeholders the drafting prompt permits), and sends it to every
confirmed, active subscriber in one action. If drafting fails, the
approval itself still records (a tenant should not be stuck over a model
outage) but nothing is released or sent — `review_action` stays
`not_available` and the tenant can retry from the notice page.

### Delivery log ([NOTIFICATION])

Every send attempt becomes a `notification_recipients` row (the frozen
recipient-list snapshot — `recipient_count` is just its size). Resend's
webhooks (`POST /webhooks/resend`, signed the same way Resend signs every
webhook — `svix-id`/`svix-timestamp`/`svix-signature`, verified against
`RESEND_WEBHOOK_SECRET` before anything is written, unverified requests
get a 401 and touch no log) append `notification_delivery_events` rows,
deduplicated on Resend's own delivery id so a retried webhook is never
recorded twice.

Current status per recipient is *derived* from that log
(`app/services/notifications.py::derive_recipient_status`), never stored
as a separately-updated column that could drift from it. Out-of-order
events resolve by precedence, not by arrival time: a bounce/failure is
sticky (a late-arriving "delivered" for the same attempt is noise, not a
correction) unless a human marks it manually resolved, or a manual resend
starts a fresh attempt whose own events take over. `delivered_count`/
`bounced_count` are computed fresh at manifest-generation time from
whatever the log says right now — never frozen, unlike the notice text
above.

Open/click tracking has no per-request field in Resend's send API (it is
a domain-level dashboard setting, off by default) — this is enforced by
never adding a tracking-related key to the send payload, checked by
`tests/test_mailer.py`'s static assertion on that payload, and needs one
external check: that tracking is not enabled in the Resend dashboard's
Configuration tab for our sending domain.

**Redacted vs. full delivery log**: `delivery_log.csv` (default; email
local-parts masked, e.g. `j***@acme.com`) or `delivery_log_full.csv` (real
addresses, gated behind an explicit checkbox and confirmation in the
dashboard) — the variant is encoded in the filename `delivery_log_file`
already names, not a new schema field, since a tenant's own customers'
addresses are exactly the kind of thing a DPO would refuse to hand an
auditor by default.

**Bounces are a real compliance gap**, surfaced with a resend action and a
"mark manually resolved" annotation (who, when, an optional note) — the
manifest's `bounced_count` still counts a resolved bounce, since the
notice genuinely never arrived through this channel; the annotation
records how it was handled outside TrustPages, not that it didn't happen.

### Objection window ([OBJECTION WINDOW])

`window_days` comes from `Tenant.objection_window_days` (configurable,
default 30 — never hardcoded, since the actual number is whatever the
tenant's own DPA promises) at the moment the window opens, which is
`sent_at` (the notice actually going out), not the moment of approval. No
recipients means the window never opens: `objection_status` reads
`not_available` with a reason shown in the dashboard, never a false
"no objection recorded" for a notice that was never sent.

Manually-recorded objections (`Objection` — arriving by email or phone in
real life, never through this product) always carry who objected
(free text) and, separately, who entered the record (`recorded_by_email`,
the authenticated tenant identity, never client-supplied). A recorded
objection overrides the "window open"/"no objection" wording regardless
of whether the window has actually closed yet — it is the single most
important fact this section can report.

## manifest.sha256 and README.txt

`[PACK CONTENTS]` makes the pack self-describing — an auditor with only
the ZIP can verify every file's hash without trusting anything else. That
list can't include `manifest.txt`'s own hash (a file cannot hash itself),
so:

- `manifest.txt` is excluded from its own `[PACK CONTENTS]` listing.
- A separate file, **`manifest.sha256`**, is added to the ZIP containing
  just the hex SHA-256 digest of `manifest.txt`'s bytes (plus a trailing
  newline).
- **`README.txt`** (≤25 lines, plain English) orients an auditor who opens
  the ZIP without any TrustPages context: what each file is, how to run
  `verify.sh`, and — for a pack with no independent timestamp — that this
  isn't a failure, just something the pack predates or couldn't obtain
  (`[TIMESTAMP]`'s `timestamp_status` says which).
- **`verify.sh`** (POSIX sh, `openssl` only, no network access) ships in
  every pack — timestamped or not. It re-hashes `after.html` and compares
  against `manifest.txt`, then (only if `timestamp_status: timestamped`)
  checks the `.tsr` token against the bundled `tsa-chain.pem` sitting next
  to it. Output is exactly one line:
  - `PASS - content hash matches and timestamp verified (<UTC>)` (exit 0)
  - `FAIL - <reason>` (exit 1)
  - `NO TIMESTAMP - pack predates independent timestamping; content hash
    matches` (exit 0 — **this is not a failure**, just the honest state of
    a pack that has no independent timestamp)
- **`after.html.sha256.tsr`** and **`tsa-chain.pem`** are added to the ZIP
  ONLY when `timestamp_status: timestamped` — there is nothing to include
  otherwise, and `[TIMESTAMP]`'s other four fields read `not_available`
  precisely because these files don't exist for this pack.

## /verify

A public, unauthenticated page (`app/routers/verify.py`,
`app/services/verify.py`) that runs the same check `verify.sh` does,
server-side, for someone who'd rather not run a shell script. Two input
modes: upload the whole `.zip`, or a captured file plus its `.tsr` token.

Hard constraints, enforced structurally, not just by convention:

- **Never touches the database.** No import of `AsyncSession`,
  `get_db_session`, or any `select(...)` anywhere in
  `app/services/verify.py` — checked by a static test
  (`tests/test_verify.py::TestNeverTouchesTheDatabaseOrDisk`) as well as by
  the route functions simply declaring no database dependency at all. A
  hash → tenant/vendor lookup here would let anyone probe "does company X
  monitor vendor Y", which is a data leak this page must be structurally
  incapable of.
- **Never trusts an uploaded CA chain** — same rule as `verify.sh` above,
  for the same reason: only `app/static_data/tsa/*.pem` is ever consulted
  for verification, regardless of what a `.zip` or a paired upload
  contains.
- **Nothing uploaded is written to permanent disk or logged.** A token
  that must reach `openssl` on the filesystem goes into a
  `tempfile.TemporaryDirectory()`, deleted before the response is sent.
- **Size- and zip-bomb-limited**: 5 MB per upload, and — before any entry
  is decompressed — a cap on total entry count and on both total and
  per-entry uncompressed size.
- **Reads both v1 and v2 packs** via the same `detect_manifest_version`
  used everywhere else. A v1 pack (no independent timestamp ever existed
  for it) is reported the same honest way `verify.sh` reports a pre-TSA
  v2 pack — not an error.

## Signing

No signing scheme exists in this codebase today (checked: no `sign`,
`signature`, or `hmac` usage anywhere in `app/services/evidence.py` or the
dashboard routes that call it). `manifest.sha256` is a plain content-hash
file, not a cryptographic signature — there is nothing here to "preserve
the mechanism of" because no mechanism currently exists.

**No signature is being added here, deliberately.** A signature made with
TrustPages' own key would carry the same epistemic weight as the SHA-256
digest already does — "TrustPages says this is what it captured" — since
both are things only TrustPages controls. It would not be independent
proof of anything a self-hashed file doesn't already claim. The actual
independent corroboration is PR 3's RFC 3161 timestamp token, issued by a
third-party TSA that TrustPages doesn't control. Every place in product
copy that used to say "signed manifest" has been corrected to describe
what the file actually is (`manifest.txt` with SHA-256 digests of every
file) rather than implying a cryptographic guarantee that doesn't exist —
see the PR description for the full list of what changed.

## Backward compatibility (non-negotiable)

Packs already downloaded by real tenants are v1 (no `manifest_version`
field, header line `TrustPages — audit evidence for one detected change`).
Their verifiability must never break:

- **`detect_manifest_version(text)`** returns `1` for any manifest with no
  `manifest_version` field, and the integer the field names otherwise. This
  is the one branch point any reader — this app's, or a third party's tool
  — uses; there is no default that assumes v2.
- Every future piece of verification code (including PR 3's `/verify`
  page) must branch on this and handle both. There is no code path in this
  codebase, now or ever, that takes v1 text and produces v2 text — v1 packs
  are read as-is, never regenerated, converted, or "upgraded". A test
  (`test_v1_packs_are_never_regenerated_or_upgraded`) exists specifically
  as a trip-wire against that ever being added by accident.

## Changelog (pre-deploy only — see the frozen-schema note at the top)

- **v2 draft 4 (PR 4):** `[REVIEW]`, `[NOTIFICATION]`, `[OBJECTION WINDOW]`
  filled in — no field names/order changed from draft 3. Every field this
  schema names is now real data or `not_available`; none is left waiting
  on a future PR.
- **v2 draft 3 (PR 3):** `[TIMESTAMP]` filled in — `timestamp_status`,
  `tsa_token_file`, `tsa_authority_url`, `tsa_time_utc`, `tsa_chain_file`.
  No field names/order changed from draft 2 — only what was previously an
  all-`not_available` section now carries real values when
  `timestamp_status: timestamped`.
- **v2 draft 2:** `review_action`'s permitted values changed from
  `approved_for_notification` / `auto_published_cosmetic` to
  `notice_released_by_reviewer` / `auto_published_cosmetic` (the old value
  collided with the forbidden-terms list). `raw_text_file`/`raw_text_sha256`
  (one field, pointing only at `after.txt`) replaced with symmetric
  `before_text_file`/`before_text_sha256`/`after_text_file`/`after_text_sha256`
  (`before.txt` had no schema counterpart before this). Both fixed before
  any production deploy of this schema.
- **v2 draft 1:** initial freeze.

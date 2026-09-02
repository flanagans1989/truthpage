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

  **Known tension, flagged for PR 4:** the schema's own `review_action`
  field takes the value `approved_for_notification` (see below), which
  contains the substring "approved". PR 2's own output never triggers this
  (`review_action` stays `not_available` until PR 4), so the forbidden-term
  scan is a simple whole-text substring check for now. PR 4 will need to
  either exempt structured enum field *values* from this scan (as opposed
  to prose fields, which is what the rule is actually protecting) or
  rename the enum value — that decision is for PR 4's review, not assumed
  here.
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
diff_file:
diff_sha256:
raw_text_file:
raw_text_sha256:

[TIMESTAMP]                      # PR 3 fills this in
timestamp_status:                # timestamped | pending | failed | not_available (pre-TSA)
tsa_token_file:
tsa_authority_url:
tsa_time_utc:
tsa_chain_file:
verification_instructions: See README.txt — run ./verify.sh offline.

[REVIEW]                         # PR 4 fills this in
reviewed_by_name:
reviewed_by_email:
reviewed_at:
review_action:                   # approved_for_notification | auto_published_cosmetic

[NOTIFICATION]                   # PR 4 fills this in
notice_frozen_at:
notice_file:
sent_at:
recipient_count:
delivered_count:
bounced_count:
delivery_log_file:

[OBJECTION WINDOW]               # PR 4 fills this in
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

## Field notes (what this PR — PR 2 — actually fills in)

Everything in `[SUBJECT]`, `[DETECTION]`, `[EVIDENCE]`, and
`[PACK CONTENTS]` is populated from data that already exists today.
`[TIMESTAMP]`, `[REVIEW]`, `[NOTIFICATION]`, and `[OBJECTION WINDOW]` are
`not_available` in every field until PR 3 / PR 4 land — see the table in
that PR's description for exactly which PR fills which field.

A few fields worth calling out:

- **`previous_snapshot_captured_at`** is `not_available` even for a fresh
  event today: the pipeline only records the *moment a change was
  detected* (`ChangeEvent.created_at`), not a separately-stored "the prior
  snapshot was captured at time X". Adding that would be new data
  collection, out of scope for a format-only PR.
- **`current_snapshot_captured_at`** reuses `detected_at` — in the current
  pipeline, detection and current-snapshot-capture are the same instant.
- **`raw_text_file` / `raw_text_sha256`** point at `after.txt` — the
  current (post-change) normalized text — the same "current state" framing
  as `after_html_file`/`after_sha256`. `before.txt` is still a real file in
  the ZIP and still listed (with its own hash) under `[PACK CONTENTS]`; it
  just has no dedicated shortcut field of its own in `[EVIDENCE]`. If a
  `before_text_sha256`-style field is wanted, that's a schema change for a
  future PR to propose, not an assumption made silently here.
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

## manifest.sha256 and README.txt

`[PACK CONTENTS]` makes the pack self-describing — an auditor with only
the ZIP can verify every file's hash without trusting anything else. That
list can't include `manifest.txt`'s own hash (a file cannot hash itself),
so:

- `manifest.txt` is excluded from its own `[PACK CONTENTS]` listing.
- A separate file, **`manifest.sha256`**, is added to the ZIP containing
  just the hex SHA-256 digest of `manifest.txt`'s bytes (plus a trailing
  newline).
- **`README.txt`** (≤20 lines, plain English) orients an auditor who opens
  the ZIP without any TrustPages context: what each file is, how to check
  a hash, and — already, ahead of PR 3 shipping — that packs generated
  before RFC 3161 timestamping have no independent proof of *when* the
  capture happened (`[TIMESTAMP]` reads `not_available`).

## Signing

No signing scheme exists in this codebase today (checked: no `sign`,
`signature`, or `hmac` usage anywhere in `app/services/evidence.py` or the
dashboard routes that call it). `manifest.sha256` is a plain content-hash
file, not a cryptographic signature — there is nothing here to "preserve
the mechanism of" because no mechanism currently exists. If a signing
requirement was assumed to already exist, it doesn't; this is worth
confirming before PR 3 builds anything that assumes otherwise.

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

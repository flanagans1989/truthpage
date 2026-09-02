# TSA CA chains

One file per timestamp authority, named after its hostname (the host in
`TSA_PRIMARY_URL`/`TSA_FALLBACK_URL`) — e.g. `https://freetsa.org/tsr` →
`freetsa.org.pem`. Each file is that authority's root CA certificate
concatenated with its TSA signing certificate, fetched from the
authority's own published files (never a third-party mirror), so a ZIP is
buildable and `/verify` is checkable even if the authority's site is down.

`app/core/tsa_chains.py` resolves an authority URL to its file here, and
`app/services/evidence.py`/`app/services/verify.py` use that resolution —
never a chain bundled inside an uploaded pack itself (see both modules'
docstrings for why).

## Never delete a file here

A token issued by an authority is verified against the chain that was
valid *when the token was issued* — not against whatever the authority's
current chain happens to be. If an authority is ever retired from
`TSA_PRIMARY_URL`/`TSA_FALLBACK_URL`, every token it already issued still
needs its file to stay here, forever, or every pack it stamped becomes
permanently unverifiable. Adding a new authority means adding a file here;
removing one from configuration never means removing its file.

"""What the site claims must be what the code can actually deliver.

Three claims were doing work they could not back:

- "tamper-proof SHA-256 evidence". We compute the digest, we store the
  file, and both live in our own database — so the digest shows a download
  matches our record, not that the record was never regenerated. Only the
  RFC 3161 token, issued by an external authority, fixes a record in time,
  and it is conditional (tsa_status can be failed or not_available).
- "Every page here is re-read daily", on a public directory whose rows
  gave a reader no way to tell a current list from a frozen one.
- A 14-day money-back guarantee shown only on the Growth card, while the
  refund policy grants it on any first paid period.

And one claim was missing entirely: we process our customers' subscriber
addresses on their behalf, which makes us their processor, and there was
no DPA anywhere on the site.
"""
import json
import pathlib

LOCALES = pathlib.Path(__file__).resolve().parents[1] / "locales"
TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / "templates"

# Every language's way of saying the thing we cannot support.
OVERCLAIMS = (
    "tamper-proof",
    "tamper proof",
    "manipulationssicher",
    "fälschungssicher",
    "infalsifiable",
    "inviolable",
    "a prueba de manipulaciones",
    "inalterable",
)


def test_no_locale_claims_the_evidence_is_tamper_proof():
    for path in sorted(LOCALES.glob("*.json")):
        blob = json.dumps(json.loads(path.read_text(encoding="utf-8")), ensure_ascii=False).lower()
        for phrase in OVERCLAIMS:
            assert phrase not in blob, f"{path.name} still claims '{phrase}'"


def test_the_digest_is_not_presented_as_proof_of_when():
    evidence = (TEMPLATES / "evidence.html").read_text(encoding="utf-8")
    assert "Cryptographically Verified Snapshot" not in evidence
    # It must point at the thing that DOES involve someone other than us.
    assert "RFC 3161" in evidence


def test_dpa_is_published_and_covers_article_28_3(anon_client):
    response = anon_client.get("/dpa")
    assert response.status_code == 200
    body = response.text
    for required in (
        "controller",
        "processor",
        "Sub-processors",
        "Standard Contractual Clauses",
        "personal data breach",
        "audit",
    ):
        assert required in body, f"DPA is missing: {required}"


def test_dpa_is_reachable_from_the_footer(anon_client):
    assert '/dpa"' in anon_client.get("/pricing").text


def test_terms_state_a_governing_law_and_our_processor_role(anon_client):
    body = anon_client.get("/terms").text
    assert "Governing law" in body
    assert "we act as your processor" in body
    assert "/dpa" in body


def test_the_refund_guarantee_is_shown_on_every_paid_plan():
    """One card carrying it and a policy granting it to both is a
    contradiction that gets read against us in a payment dispute."""
    template = (TEMPLATES / "pricing.html").read_text(encoding="utf-8")
    starter_card, _, growth_card = template.partition("pricing.growth_name")
    assert "pricing.growth_guarantee" in starter_card
    assert "pricing.growth_guarantee" in growth_card


def test_the_directory_carries_a_disclaimer(anon_client):
    body = anon_client.get("/vendors").text
    assert "not an official statement by the vendor" in body

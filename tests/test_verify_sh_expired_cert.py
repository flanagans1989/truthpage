"""Item 6a follow-up: verify.sh must still PASS for a token whose signing
certificate's own validity window has since passed — a timestamp attests
the digest existed when the token was issued, which does not expire just
because the certificate that made the attestation later does.

Builds a genuinely self-signed, throwaway TSA whose certificate expired
one hour before this test runs (via openssl's -not_before/-not_after),
issues a real RFC 3161 token with it, and confirms:
  (a) without -no_check_time, `openssl ts -verify` correctly reports the
      certificate as expired (proving this is a real scenario, not a
      no-op check), and
  (b) the actual verify.sh shipped in evidence.py still reports PASS.

Fully offline — no network, no real TSA. Skipped if openssl is missing,
same as tests/test_verify_sh.py.
"""
import hashlib
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.services.evidence import _verify_sh

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not available in this environment")

_DIGEST_CONTENT = b"<html>content whose digest gets an expired-cert timestamp</html>"
_DIGEST_HEX = hashlib.sha256(_DIGEST_CONTENT).hexdigest()


def _run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=30, **kwargs)


def _openssl_time(dt: datetime) -> str:
    return dt.strftime("%y%m%d%H%M%SZ")


@pytest.fixture
def expired_tsa_chain_and_token(tmp_path: Path) -> tuple[Path, Path]:
    """Returns (chain_path, token_path) for a real RFC 3161 token whose
    signing certificate's notAfter is one hour before "now".

    Uses `openssl ca` with -startdate/-enddate rather than `x509 -req`'s
    -not_before/-not_after (only supported by newer OpenSSL point
    releases) — the `ca` subcommand's start/end-date override has been
    portable since long before OpenSSL 3.0, which is what actually matters
    for this to run the same way in CI as it does locally.
    """
    root_key = tmp_path / "root.key"
    root_pem = tmp_path / "root.pem"
    tsa_key = tmp_path / "tsa.key"
    tsa_csr = tmp_path / "tsa.csr"
    tsa_pem = tmp_path / "tsa.pem"
    tsa_ext = tmp_path / "tsa.ext"
    tsa_cnf = tmp_path / "tsa.cnf"
    serial = tmp_path / "tsaserial"
    query = tmp_path / "query.tsq"
    reply = tmp_path / "reply.tsr"
    chain = tmp_path / "chain.pem"

    env = {"MSYS_NO_PATHCONV": "1", **__import__("os").environ}

    assert _run(["openssl", "genrsa", "-out", str(root_key), "2048"], env=env).returncode == 0
    assert _run(
        ["openssl", "req", "-x509", "-new", "-key", str(root_key), "-out", str(root_pem),
         "-days", "7300", "-subj", "/CN=TrustPages Test Root CA (throwaway)", "-sha256"],
        env=env,
    ).returncode == 0
    assert _run(["openssl", "genrsa", "-out", str(tsa_key), "2048"], env=env).returncode == 0
    assert _run(
        ["openssl", "req", "-new", "-key", str(tsa_key), "-out", str(tsa_csr),
         "-subj", "/CN=TrustPages Test TSA (throwaway, expired)", "-sha256"],
        env=env,
    ).returncode == 0

    tsa_ext.write_text("basicConstraints=critical,CA:FALSE\nextendedKeyUsage=critical,timeStamping\n")

    # Minimal CA database `openssl ca` requires to exist, even though this
    # test never reads it back.
    (tmp_path / "index.txt").write_text("")
    (tmp_path / "newcerts").mkdir()
    ca_serial = tmp_path / "ca_serial"
    ca_serial.write_text("1000\n")
    ca_cnf = tmp_path / "ca.cnf"
    ca_cnf.write_text(f"""[ ca ]
default_ca = CA_default

[ CA_default ]
dir = {tmp_path.as_posix()}
database = {(tmp_path / "index.txt").as_posix()}
new_certs_dir = {(tmp_path / "newcerts").as_posix()}
certificate = {root_pem.as_posix()}
private_key = {root_key.as_posix()}
serial = {ca_serial.as_posix()}
default_md = sha256
policy = policy_any
email_in_dn = no
copy_extensions = none
unique_subject = no

[ policy_any ]
commonName = supplied
""")

    now = datetime.now(UTC)
    not_before = _openssl_time(now - timedelta(days=2))
    not_after = _openssl_time(now - timedelta(hours=1))  # expired one hour ago

    result = _run(
        ["openssl", "ca", "-config", str(ca_cnf), "-batch", "-notext",
         "-startdate", not_before, "-enddate", not_after,
         "-extfile", str(tsa_ext), "-in", str(tsa_csr), "-out", str(tsa_pem)],
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    # Sanity-check the fixture itself really is expired as of "now".
    dates = _run(["openssl", "x509", "-in", str(tsa_pem), "-noout", "-dates"], env=env)
    assert "notAfter=" in dates.stdout.decode()

    tsa_cnf.write_text(f"""[ tsa ]
default_tsa = tsa_config1

[ tsa_config1 ]
dir = {tmp_path.as_posix()}
serial = {serial.as_posix()}
signer_cert = {tsa_pem.as_posix()}
certs = {root_pem.as_posix()}
signer_key = {tsa_key.as_posix()}
signer_digest = sha256
default_policy = 1.2.3.4.1
digests = sha256
accuracy = secs:1
clock_precision_digits = 0
ordering = yes
tsa_name = yes
ess_cert_id_valid = yes
ess_cert_id_alg = sha256
""")
    serial.write_text("01\n")

    assert _run(
        ["openssl", "ts", "-query", "-digest", _DIGEST_HEX, "-sha256", "-cert", "-no_nonce", "-out", str(query)],
        env=env,
    ).returncode == 0
    reply_result = _run(
        ["openssl", "ts", "-reply", "-config", str(tsa_cnf), "-queryfile", str(query), "-out", str(reply)],
        env=env,
    )
    assert reply_result.returncode == 0, reply_result.stderr
    assert reply.stat().st_size > 0

    chain.write_bytes(root_pem.read_bytes() + tsa_pem.read_bytes())
    return chain, reply


class TestNoCheckTimeIsActuallyNecessary:
    def test_without_no_check_time_openssl_reports_the_cert_as_expired(self, expired_tsa_chain_and_token):
        chain, token = expired_tsa_chain_and_token
        result = _run(["openssl", "ts", "-verify", "-in", str(token), "-digest", _DIGEST_HEX, "-CAfile", str(chain)])
        combined = (result.stdout + result.stderr).decode()
        assert "Verification: FAILED" in combined
        assert "expired" in combined.lower()

    def test_with_no_check_time_openssl_reports_ok(self, expired_tsa_chain_and_token):
        chain, token = expired_tsa_chain_and_token
        result = _run([
            "openssl", "ts", "-verify", "-in", str(token), "-digest", _DIGEST_HEX,
            "-CAfile", str(chain), "-no_check_time",
        ])
        assert b"Verification: OK" in result.stdout


class TestVerifyShPassesPastCertExpiry:
    def test_verify_sh_still_passes_one_hour_after_the_signing_cert_expired(
        self, tmp_path: Path, expired_tsa_chain_and_token
    ):
        chain, token = expired_tsa_chain_and_token

        after_html = tmp_path / "after.html"
        after_html.write_bytes(_DIGEST_CONTENT)
        (tmp_path / "after.html.sha256.tsr").write_bytes(token.read_bytes())
        chain_filename = "expired-test-tsa.pem"
        (tmp_path / chain_filename).write_bytes(chain.read_bytes())

        manifest = tmp_path / "manifest.txt"
        manifest.write_text(
            "TrustPages Audit Evidence Pack\n"
            "manifest_version: 2\n\n"
            "[EVIDENCE]\n"
            "after_html_file: after.html\n"
            f"after_sha256: {_DIGEST_HEX}\n\n"
            "[TIMESTAMP]\n"
            "timestamp_status: timestamped\n"
            "tsa_token_file: after.html.sha256.tsr\n"
            f"tsa_chain_file: {chain_filename}\n"
            "tsa_time_utc: 2026-08-31T19:19:34Z\n"
        )
        (tmp_path / "verify.sh").write_text(_verify_sh())

        result = subprocess.run(
            ["sh", str(tmp_path / "verify.sh")], capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        output = result.stdout.strip()
        assert output.startswith("PASS")
        assert len(output.splitlines()) == 1
        # The cert window printed is the EXPIRED one, proving the script
        # actually inspected the real (past-expiry) certificate rather
        # than silently skipping that part.
        assert "notAfter=" in output


class TestVerifyPyPassesPastCertExpiry:
    """Same fix, same guarantee, on the server-side /verify path — the two
    must never disagree about whether an old token still verifies."""

    def test_verify_content_and_token_still_passes_one_hour_after_expiry(
        self, monkeypatch, expired_tsa_chain_and_token
    ):
        import app.core.tsa_chains as tsa_chains_mod
        from app.services.verify import verify_content_and_token

        chain, token = expired_tsa_chain_and_token
        monkeypatch.setattr(tsa_chains_mod, "all_bundled_chain_paths", lambda: [chain])
        monkeypatch.setattr("app.services.verify.all_bundled_chain_paths", lambda: [chain])

        result = verify_content_and_token(_DIGEST_CONTENT, token.read_bytes())
        assert result.ok is True
        assert result.tsa_cert_window is not None
        assert "notAfter=" in result.tsa_cert_window

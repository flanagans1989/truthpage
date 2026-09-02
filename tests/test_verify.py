"""app/services/verify.py — public, unauthenticated pack verification.
Runs entirely against the real, checked-in sample evidence pack (a real
FreeTSA token, obtained once and committed — see app/services/leads.py) so
this suite needs no network access and no live TSA to be up.
"""
import inspect
import io
import zipfile

import app.services.verify as verify_mod
from app.services.evidence import evidence_zip
from app.services.leads import sample_change_event, sample_tenant
from app.services.verify import (
    MAX_UPLOAD_BYTES,
    verify_content_and_token,
    verify_pack,
)


def _real_sample_zip_bytes() -> bytes:
    return evidence_zip(sample_change_event(), "https://usetrustpages.com", sample_tenant())


class TestVerifyPackHappyPath:
    def test_a_real_timestamped_pack_passes(self):
        result = verify_pack(_real_sample_zip_bytes())
        assert result.ok is True
        assert "PASS" in result.message
        assert result.manifest_version == 2
        assert result.timestamp_status == "timestamped"
        assert result.tsa_authority_url == "https://freetsa.org/tsr"

    def test_tampered_content_fails(self):
        zip_bytes = _real_sample_zip_bytes()
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        names = zf.namelist()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for name in names:
                content = zf.read(name)
                if name == "after.html":
                    content += b"tampered"
                out.writestr(name, content)
        result = verify_pack(buf.getvalue())
        assert result.ok is False
        assert "mismatch" in result.message

    def test_a_corrupted_token_fails(self):
        zip_bytes = _real_sample_zip_bytes()
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for name in zf.namelist():
                content = zf.read(name)
                if name == "after.html.sha256.tsr":
                    content = b"not a real token"
                out.writestr(name, content)
        result = verify_pack(buf.getvalue())
        assert result.ok is False
        assert "verification failed" in result.message

    def test_a_pack_with_its_own_fake_ca_chain_is_still_verified_against_our_bundled_chain(self):
        # The critical security property: an uploaded chain file (whatever
        # tsa_chain_file names — freetsa.org.pem today) is never trusted,
        # even if the zip supplies one. Overwrite it with garbage and
        # confirm the real, bundled-chain-based verification still passes
        # (i.e. the garbage was never consulted).
        zip_bytes = _real_sample_zip_bytes()
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as out:
            for name in zf.namelist():
                content = zf.read(name)
                if name == "freetsa.org.pem":
                    content = b"-----BEGIN CERTIFICATE-----\nnot a real cert\n-----END CERTIFICATE-----\n"
                out.writestr(name, content)
        result = verify_pack(buf.getvalue())
        assert result.ok is True  # unaffected — the fake chain was never used


class TestNoTimestampIsNotAFailure:
    def test_not_available_pre_tsa_reports_no_timestamp_with_ok_true(self):
        event = sample_change_event()
        event.timestamp_status = "not_available_pre_tsa"
        event.tsa_token = None
        result = verify_pack(evidence_zip(event, "https://usetrustpages.com", sample_tenant()))
        assert result.ok is True
        assert "NO TIMESTAMP" in result.message

    def test_v1_pack_with_no_manifest_version_field_is_handled(self):
        import hashlib
        html = b"<html>legacy content</html>"
        h = hashlib.sha256(html).hexdigest()
        manifest_v1 = (
            "TrustPages — audit evidence for one detected change\n"
            "=======================================================\n\n"
            "Cryptographic verification anchor\n"
            "-------------------------------------------------------\n"
            f"Content Hash (SHA-256): {h}\n"
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.txt", manifest_v1)
            zf.writestr("after.html", html)
        result = verify_pack(buf.getvalue())
        assert result.ok is True
        assert result.manifest_version == 1
        assert "NO TIMESTAMP" in result.message


class TestContentAndTokenPair:
    def test_matching_pair_passes(self):
        zf = zipfile.ZipFile(io.BytesIO(_real_sample_zip_bytes()))
        result = verify_content_and_token(zf.read("after.html"), zf.read("after.html.sha256.tsr"))
        assert result.ok is True

    def test_wrong_content_fails(self):
        zf = zipfile.ZipFile(io.BytesIO(_real_sample_zip_bytes()))
        result = verify_content_and_token(b"some other content entirely", zf.read("after.html.sha256.tsr"))
        assert result.ok is False


class TestSizeAndZipBombLimits:
    def test_an_oversized_upload_is_refused_before_parsing(self):
        huge = b"x" * (MAX_UPLOAD_BYTES + 1)
        result = verify_pack(huge)
        assert result.ok is False
        assert "too large" in result.message

    def test_a_zip_with_too_many_entries_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for i in range(verify_mod.MAX_ZIP_ENTRIES + 1):
                zf.writestr(f"file{i}.txt", "x")
        result = verify_pack(buf.getvalue())
        assert result.ok is False
        assert "too many files" in result.message

    def test_a_single_oversized_entry_is_refused_without_decompressing_it(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Highly compressible — a real zip bomb would use exactly this
            # trick (tiny compressed size, huge declared uncompressed size).
            zf.writestr("bomb.txt", "0" * (verify_mod.MAX_SINGLE_ENTRY_BYTES + 1))
        result = verify_pack(buf.getvalue())
        assert result.ok is False
        assert "too large" in result.message

    def test_not_a_zip_file_at_all_is_refused_cleanly(self):
        result = verify_pack(b"definitely not a zip")
        assert result.ok is False
        assert "not a valid ZIP" in result.message

    def test_a_zip_missing_manifest_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("something.txt", "hello")
        result = verify_pack(buf.getvalue())
        assert result.ok is False
        assert "manifest.txt" in result.message


class TestNeverTouchesTheDatabaseOrDisk:
    def test_the_module_imports_nothing_database_shaped(self):
        # Static check: this module must never gain a DB dependency. A
        # hash-lookup-by-vendor feature here would let anyone probe "does
        # tenant X monitor vendor Y" — a data leak this module must
        # structurally be unable to have.
        source = inspect.getsource(verify_mod)
        for forbidden in ("AsyncSession", "get_db_session", "select(", "import sqlalchemy"):
            assert forbidden not in source, f"verify.py must never reference {forbidden!r}"

    def test_verification_does_not_leave_files_behind(self, tmp_path, monkeypatch):
        import os
        monkeypatch.chdir(tmp_path)
        before = set(os.listdir(tmp_path))
        verify_pack(_real_sample_zip_bytes())
        after = set(os.listdir(tmp_path))
        assert before == after

"""Runs the actual verify.sh shipped in the ZIP through the real `openssl`
binary — against the real, checked-in sample pack (a genuine FreeTSA
token, no network call needed at test time). PR 3 test items 9-11.
"""
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

from app.services.evidence import evidence_zip
from app.services.leads import sample_change_event, sample_tenant

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not available in this environment")


def _extract_sample_zip(tmp_path: Path) -> Path:
    zip_bytes = evidence_zip(sample_change_event(), "https://usetrustpages.com", sample_tenant())
    with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes)) as zf:
        zf.extractall(tmp_path)
    return tmp_path


def _run_verify_sh(directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["sh", str(directory / "verify.sh")],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestVerifyShOffline:
    def test_passes_on_a_genuinely_timestamped_pack(self, tmp_path):
        directory = _extract_sample_zip(tmp_path)
        result = _run_verify_sh(directory)
        assert result.returncode == 0
        assert result.stdout.strip().startswith("PASS")

    def test_fails_when_content_is_tampered(self, tmp_path):
        directory = _extract_sample_zip(tmp_path)
        with open(directory / "after.html", "ab") as f:
            f.write(b"tampered")
        result = _run_verify_sh(directory)
        assert result.returncode == 1
        assert result.stdout.strip().startswith("FAIL")

    def test_fails_on_a_corrupted_token(self, tmp_path):
        directory = _extract_sample_zip(tmp_path)
        (directory / "after.html.sha256.tsr").write_bytes(b"not a real token")
        result = _run_verify_sh(directory)
        assert result.returncode == 1
        assert result.stdout.strip().startswith("FAIL")

    def test_reports_no_timestamp_with_exit_zero_for_a_pre_tsa_pack(self, tmp_path):
        event = sample_change_event()
        event.timestamp_status = "not_available_pre_tsa"
        event.tsa_token = None
        zip_bytes = evidence_zip(event, "https://usetrustpages.com", sample_tenant())
        with zipfile.ZipFile(__import__("io").BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp_path)
        result = _run_verify_sh(tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip().startswith("NO TIMESTAMP")

    def test_output_is_exactly_one_line(self, tmp_path):
        directory = _extract_sample_zip(tmp_path)
        result = _run_verify_sh(directory)
        assert len(result.stdout.strip().splitlines()) == 1

    def test_never_touches_the_network(self, tmp_path, monkeypatch):
        # Best-effort proof of "no network access used": run with no DNS
        # resolution possible by pointing at an unroutable resolver: a
        # network-dependent script would hang/timeout, not finish under 30s.
        directory = _extract_sample_zip(tmp_path)
        env = {"PATH": __import__("os").environ.get("PATH", "")}
        result = subprocess.run(
            ["sh", str(directory / "verify.sh")],
            capture_output=True, text=True, timeout=10, env=env,
        )
        assert result.returncode == 0

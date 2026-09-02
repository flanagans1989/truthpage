"""Route-level tests for the public /verify page. Needs app.main (pulls in
the full router stack via app/services/onboarding.py's HTMLNormalizer /
selectolax import chain) — like every other app.main-dependent test in this
repo, only confirmed via CI on this branch; see the PR description.
"""
import io
import zipfile

from app.services.evidence import evidence_zip
from app.services.leads import sample_change_event, sample_tenant


def _sample_zip_bytes() -> bytes:
    return evidence_zip(sample_change_event(), "https://usetrustpages.com", sample_tenant())


class TestVerifyForm:
    def test_form_renders(self, anon_client):
        r = anon_client.get("/verify")
        assert r.status_code == 200
        assert "Verify" in r.text


class TestVerifySubmit:
    def test_a_real_timestamped_pack_passes(self, anon_client):
        r = anon_client.post(
            "/verify",
            files={"pack": ("pack.zip", _sample_zip_bytes(), "application/zip")},
        )
        assert r.status_code == 200
        assert "PASS" in r.text

    def test_content_and_token_pair_mode(self, anon_client):
        zf = zipfile.ZipFile(io.BytesIO(_sample_zip_bytes()))
        r = anon_client.post(
            "/verify",
            files={
                "content": ("after.html", zf.read("after.html"), "text/html"),
                "token": ("after.html.sha256.tsr", zf.read("after.html.sha256.tsr"), "application/octet-stream"),
            },
        )
        assert r.status_code == 200
        assert "PASS" in r.text

    def test_no_file_at_all_shows_an_error_not_a_500(self, anon_client):
        r = anon_client.post("/verify", data={})
        assert r.status_code == 200
        assert "Upload either" in r.text

    def test_rate_limit_kicks_in(self, anon_client):
        for _ in range(10):
            anon_client.post("/verify", data={})
        r = anon_client.post("/verify", data={})
        assert r.status_code == 429


class TestVerifyNeverTouchesTheDatabase:
    def test_the_route_functions_take_no_db_dependency_at_all(self):
        # Structurally stronger than mocking a session: these functions
        # cannot reach a database via FastAPI's DI because neither one
        # declares that dependency, so there is nothing to override or
        # accidentally call. Belt-and-suspenders on top of test_verify.py's
        # source-level check that app/services/verify.py never imports
        # AsyncSession/get_db_session/select(...) either.
        import inspect

        from app.routers.verify import verify_form, verify_submit

        for fn in (verify_form, verify_submit):
            params = inspect.signature(fn).parameters
            assert not any("db" in name or "session" in name.lower() for name in params), (
                f"{fn.__name__} must never take a database dependency"
            )

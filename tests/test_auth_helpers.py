import jwt
import pytest

from app.core.config import settings
from app.routers.auth import (
    _ALGORITHM,
    _email_to_company_name,
    _email_to_slug,
    _make_magic_token,
    _make_session_token,
)


def test_email_to_slug():
    assert _email_to_slug("user@acme.com") == "acme"
    assert _email_to_slug("user@sub-domain.co.uk") == "sub-domain"
    assert _email_to_slug("user@ACME.com") == "acme"


def test_email_to_company_name():
    assert _email_to_company_name("user@acme.com") == "Acme"


def test_magic_token_roundtrip_has_jti():
    token = _make_magic_token("a@b.com")
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
    assert payload["sub"] == "a@b.com"
    assert payload["type"] == "magic"
    assert payload["jti"]


def test_magic_tokens_are_unique():
    assert _make_magic_token("a@b.com") != _make_magic_token("a@b.com")


def test_session_token_type():
    token = _make_session_token("some-tenant-id")
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
    assert payload["type"] == "session"
    assert payload["sub"] == "some-tenant-id"


def test_magic_token_is_not_valid_session_token():
    """A magic token must never pass as a session cookie (type confusion)."""
    token = _make_magic_token("a@b.com")
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])
    assert payload["type"] != "session"


def test_tampered_token_rejected():
    token = _make_magic_token("a@b.com") + "x"
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, settings.JWT_SECRET, algorithms=[_ALGORITHM])

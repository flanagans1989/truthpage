import pytest
from fastapi import HTTPException

from app.routers import subprocessors as sp_mod
from app.routers.subprocessors import _validate_monitored_url


def _fake_resolver(ip: str):
    def resolver(host, port, proto=0):
        return [(2, 1, 6, "", (ip, 0))]
    return resolver


def test_rejects_non_http_schemes():
    for url in ("ftp://x.com/a", "file:///etc/passwd", "javascript:alert(1)"):
        with pytest.raises(HTTPException):
            _validate_monitored_url(url)


def test_rejects_reserved_hostnames():
    with pytest.raises(HTTPException):
        _validate_monitored_url("http://localhost/admin")
    with pytest.raises(HTTPException):
        _validate_monitored_url("http://metadata.google.internal/computeMetadata")


def test_rejects_raw_private_ips():
    for url in ("http://127.0.0.1/", "http://10.0.0.5/", "http://169.254.169.254/", "http://192.168.1.1/"):
        with pytest.raises(HTTPException):
            _validate_monitored_url(url)


def test_rejects_hostname_resolving_to_private_ip(monkeypatch):
    monkeypatch.setattr(sp_mod.socket, "getaddrinfo", _fake_resolver("169.254.169.254"))
    with pytest.raises(HTTPException):
        _validate_monitored_url("https://evil.example.com/policy")


def test_accepts_public_hostname(monkeypatch):
    monkeypatch.setattr(sp_mod.socket, "getaddrinfo", _fake_resolver("93.184.216.34"))
    _validate_monitored_url("https://example.com/privacy")  # should not raise

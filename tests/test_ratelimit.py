from app.core.ratelimit import SlidingWindowLimiter, get_client_ip


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, headers=None, client_host="10.0.0.1"):
        self.headers = headers or {}
        self.client = _FakeClient(client_host) if client_host else None


def test_get_client_ip_uses_last_forwarded_entry_not_spoofable_first():
    # Render appends the real client IP as the last hop; earlier entries
    # (like a spoofed X-Forwarded-For sent by the client) must be ignored.
    request = _FakeRequest(headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.5"})
    assert get_client_ip(request) == "203.0.113.5"


def test_get_client_ip_falls_back_to_socket_when_no_header():
    request = _FakeRequest(headers={}, client_host="192.168.1.1")
    assert get_client_ip(request) == "192.168.1.1"


def test_allows_up_to_max_then_blocks():
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=60)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False


def test_keys_are_independent():
    limiter = SlidingWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False

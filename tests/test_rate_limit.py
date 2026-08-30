"""
Covers the per-IP rate limiter (app/rate_limit.py) that guards the public
register and cover-art endpoints against brute-force link-ID guessing.
"""

import pytest
from fastapi import HTTPException

from app.rate_limit import client_ip, rate_limiter


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, ip, headers=None):
        self.headers = headers or {}
        self.client = _FakeClient(ip)


def test_rate_limiter_allows_up_to_the_limit():
    limiter = rate_limiter(max_requests=3, window_s=60)
    req = _FakeRequest("1.2.3.4")
    for _ in range(3):
        limiter(req)  # must not raise


def test_rate_limiter_blocks_the_next_request():
    limiter = rate_limiter(max_requests=3, window_s=60)
    req = _FakeRequest("1.2.3.4")
    for _ in range(3):
        limiter(req)
    with pytest.raises(HTTPException) as exc_info:
        limiter(req)
    assert exc_info.value.status_code == 429


def test_rate_limiter_tracks_ips_independently():
    limiter = rate_limiter(max_requests=1, window_s=60)
    limiter(_FakeRequest("1.1.1.1"))
    limiter(_FakeRequest("2.2.2.2"))  # separate budget — must not raise


def test_client_ip_prefers_x_forwarded_for():
    req = _FakeRequest("10.0.0.1", headers={"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
    assert client_ip(req) == "203.0.113.5"


def test_client_ip_falls_back_to_connection_address():
    req = _FakeRequest("10.0.0.1")
    assert client_ip(req) == "10.0.0.1"

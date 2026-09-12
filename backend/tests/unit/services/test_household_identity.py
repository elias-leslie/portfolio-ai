"""Access assertions, local transport, and capture-only route boundaries."""

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from starlette.requests import Request

from app.services import household_identity as identity


@pytest.fixture
def signed_access(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(identity.settings, "cloudflare_access_aud", "portfolio-test")
    monkeypatch.setattr(
        identity,
        "_access_keys",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=key.public_key())
        ),
    )
    claims = {
        "exp": int(time.time()) + 300,
        "iat": int(time.time()),
        "iss": "https://summitflow.cloudflareaccess.com",
        "aud": ["portfolio-test"],
        "email": "member@example.invalid",
        "sub": "test-subject",
    }
    return key, claims


def test_signed_application_token_required(signed_access):
    key, claims = signed_access
    assert (
        identity.verify_access_assertion(jwt.encode(claims, key, algorithm="RS256"))["sub"]
        == "test-subject"
    )
    for update in [
        {"aud": "another-app"},
        {"iss": "https://other.example.invalid"},
        {"exp": 1},
        {"email": ""},
    ]:
        with pytest.raises(HTTPException):
            identity.verify_access_assertion(
                jwt.encode({**claims, **update}, key, algorithm="RS256")
            )
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(HTTPException):
        identity.verify_access_assertion(jwt.encode(claims, wrong_key, algorithm="RS256"))


def request(host="127.0.0.1", headers=()):
    return Request({"type": "http", "client": (host, 123), "headers": list(headers)})


def test_proxy_cannot_turn_unsigned_edge_request_into_local_operator():
    assert identity.resolve_identity(request()).access == "local_operator"
    assert (
        identity.resolve_identity(request(headers=[(b"x-forwarded-for", b"127.0.0.1")])).access
        == "local_operator"
    )
    for req in [
        request("192.0.2.1"),
        request(headers=[(b"cf-ray", b"edge")]),
        request(headers=[(b"x-forwarded-for", b"192.0.2.1")]),
        request(headers=[(b"cf-access-jwt-assertion", b"invalid")]),
    ]:
        with pytest.raises(HTTPException):
            identity.resolve_identity(req)


def test_capture_only_allowlist_does_not_grant_financial_or_review_access():
    allowed = identity.capture_path_allowed
    assert allowed("GET", "/api/identity")
    assert allowed("POST", "/api/captures")
    assert allowed("GET", "/api/captures/123/image")
    for method, path in [
        ("GET", "/api/household/dashboard"),
        ("POST", "/api/portfolio/jenny/chat"),
        ("PATCH", "/api/captures/123"),
        ("POST", "/api/captures/123/intake"),
        ("GET", "/api/captures/members"),
        ("POST", "/api/household/push/test"),
        ("GET", "/docs"),
    ]:
        assert not allowed(method, path)

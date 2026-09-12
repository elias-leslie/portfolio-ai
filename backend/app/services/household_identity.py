"""Resolve verified Access identities; never trust a caller-selected member."""

from __future__ import annotations

import ipaddress
import json
from functools import lru_cache
from typing import Any, Literal

import jwt
from fastapi import HTTPException, Request
from pydantic import BaseModel

from app.config import settings
from app.storage import get_storage


class HouseholdIdentity(BaseModel):
    member_id: str | None = None
    display_name: str
    access: Literal["adult", "capture_only", "local_operator"]


def seed_member_emails() -> int:
    """One-time assignment from private provisioning; existing DB facts win."""
    raw = settings.household_member_emails.get_secret_value()
    if not raw:
        return 0
    try:
        mapping = json.loads(raw)
        if not isinstance(mapping, dict) or not all(
            isinstance(email, str) and "@" in email and isinstance(name, str)
            for email, name in mapping.items()
        ):
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Invalid private household identity provisioning") from exc
    updated = 0
    with get_storage().connection() as conn:
        for email, name in mapping.items():
            rows = conn.execute(
                "SELECT id, email FROM household_members WHERE lower(display_name) = lower(%s)",
                [name.strip()],
            ).fetchall()
            if len(rows) != 1:
                raise RuntimeError(
                    "Household identity provisioning requires unique existing member names"
                )
            if rows[0][1] is None:
                conn.execute(
                    "UPDATE household_members SET email = %s WHERE id = %s AND email IS NULL",
                    [email.strip().lower(), rows[0][0]],
                )
                updated += 1
        conn.commit()
    return updated


@lru_cache(maxsize=1)
def _access_keys() -> jwt.PyJWKClient:
    domain = settings.cloudflare_access_team_domain.removeprefix("https://").rstrip("/")
    return jwt.PyJWKClient(f"https://{domain}/cdn-cgi/access/certs", timeout=5)


def verify_access_assertion(assertion: str) -> dict[str, Any]:
    if not settings.cloudflare_access_aud:
        raise HTTPException(
            503, "Household sign-in needs the Access application audience configured."
        )
    try:
        key = _access_keys().get_signing_key_from_jwt(assertion)
        claims = jwt.decode(
            assertion,
            key.key,
            algorithms=["RS256"],
            audience=settings.cloudflare_access_aud,
            issuer=f"https://{settings.cloudflare_access_team_domain.removeprefix('https://').rstrip('/')}",
            options={"require": ["exp", "iat", "iss", "aud", "email", "sub"]},
        )
        if not isinstance(claims.get("email"), str) or not claims["email"].strip():
            raise jwt.InvalidTokenError()
        return claims
    except jwt.PyJWTError as exc:
        raise HTTPException(403, "Household sign-in could not be verified.") from exc


def is_local_connection(request: Request) -> bool:
    try:
        return bool(request.client and ipaddress.ip_address(request.client.host).is_loopback)
    except ValueError:
        return False


def resolve_identity(request: Request) -> HouseholdIdentity:
    assertion = request.headers.get("cf-access-jwt-assertion", "").strip()
    if assertion:
        claims = verify_access_assertion(assertion)
        with get_storage().connection() as conn:
            row = conn.execute(
                "SELECT id, display_name, role, is_dependent FROM household_members WHERE lower(email) = %s",
                [claims["email"].strip().lower()],
            ).fetchone()
        if row is None:
            raise HTTPException(403, "This sign-in is not a registered household member.")
        adult = row[2] in {"primary", "spouse"} and not row[3]
        return HouseholdIdentity(
            member_id=str(row[0]), display_name=row[1], access="adult" if adult else "capture_only"
        )
    # The backend binds to loopback; Next forwards the original signed assertion.
    # An edge request missing that assertion may not inherit local authority.
    forwarded = request.headers.get("x-forwarded-for", "")
    try:
        local_forward = not forwarded or all(
            ipaddress.ip_address(value.strip()).is_loopback for value in forwarded.split(",")
        )
    except ValueError:
        local_forward = False
    if (
        is_local_connection(request)
        and local_forward
        and not any(request.headers.get(header) for header in ("cf-connecting-ip", "cf-ray"))
    ):
        return HouseholdIdentity(display_name="Local workspace", access="local_operator")
    raise HTTPException(403, "Household sign-in is required.")


def request_identity(request: Request) -> HouseholdIdentity:
    return request.state.household_identity


def require_adult(identity: HouseholdIdentity) -> None:
    if identity.access == "capture_only":
        raise HTTPException(403, "This account can capture and review its own uploads.")


def capture_path_allowed(method: str, path: str) -> bool:
    if (method, path) in {
        ("GET", "/api/captures/shopping/products"),
        ("POST", "/api/captures/shopping/compare"),
    }:
        return True
    if method == "GET" and path == "/api/identity":
        return True
    if path == "/api/captures" and method in {"GET", "POST"}:
        return True
    parts = path.strip("/").split("/")
    return (
        len(parts) == 4
        and parts[:2] == ["api", "captures"]
        and parts[3] == "image"
        and method == "GET"
    )

"""Helpers for constructing allowed frontend origins."""

from __future__ import annotations

from urllib.parse import urlparse

from . import PORTFOLIO_FRONTEND_PORT


def _local_origins(port: int) -> tuple[str, ...]:
    """Build localhost origin variants for a given port."""
    return (
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
        f"https://localhost:{port}",
        f"https://127.0.0.1:{port}",
    )


def build_cors_origins(
    frontend_host: str | None = None,
    extra_origins: str | None = None,
    *,
    frontend_url: str = f"http://localhost:{PORTFOLIO_FRONTEND_PORT}",
) -> list[str]:
    """Build the allowed frontend origins list from optional environment config.

    Args:
        frontend_host: Optional hostname to add as an extra allowed origin.
        extra_origins: Comma-separated extra origins.
        frontend_url: The configured frontend URL (from settings). Port is
            extracted from this to avoid hardcoding.
    """
    parsed = urlparse(frontend_url)
    port = parsed.port or PORTFOLIO_FRONTEND_PORT

    origins: list[str] = list(_local_origins(port))

    if frontend_host:
        origins.extend((f"http://{frontend_host}:{port}", f"https://{frontend_host}:{port}"))

    if extra_origins:
        origins.extend(origin.strip() for origin in extra_origins.split(",") if origin.strip())

    deduped: list[str] = []
    for origin in origins:
        if origin not in deduped:
            deduped.append(origin)
    return deduped

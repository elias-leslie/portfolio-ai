"""Helpers for constructing allowed frontend origins."""

from __future__ import annotations

LOCAL_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost:3000",
    "https://127.0.0.1:3000",
)
PRODUCTION_FRONTEND_ORIGIN = "https://port.summitflow.dev"


def build_cors_origins(
    frontend_host: str | None = None,
    extra_origins: str | None = None,
) -> list[str]:
    """Build the allowed frontend origins list from optional environment config."""
    origins = list(LOCAL_FRONTEND_ORIGINS)

    if frontend_host:
        origins.extend((f"http://{frontend_host}:3000", f"https://{frontend_host}:3000"))

    origins.append(PRODUCTION_FRONTEND_ORIGIN)

    if extra_origins:
        origins.extend(origin.strip() for origin in extra_origins.split(",") if origin.strip())

    deduped: list[str] = []
    for origin in origins:
        if origin not in deduped:
            deduped.append(origin)
    return deduped

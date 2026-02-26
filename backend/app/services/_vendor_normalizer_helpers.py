"""Private helpers for vendor_normalizer — not part of the public API."""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC, datetime


def extract_source_name(entry: dict[str, object]) -> str | None:
    """Extract and normalize news source name from entry."""
    value = entry.get("news_source_name") or entry.get("publisher")
    if not isinstance(value, dict):
        return str(value) if value else None
    return str(value.get("name") or value.get("title") or "") or None


def extract_published_iso(entry: dict[str, object]) -> str | None:
    """Extract and normalize published timestamp to ISO format."""
    value = entry.get("published_at") or entry.get("published")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat()
    return None


def extract_symbol(entry: dict[str, object], default_symbol: str) -> str:
    """Extract and normalize symbol from entry."""
    value = entry.get("symbol") or default_symbol
    if isinstance(value, str):
        return value.upper()
    return default_symbol.upper()


def extract_vendor_payload(
    entry: dict[str, object],
) -> dict[str, object] | list[object] | None:
    """Extract and parse vendor payload from entry."""
    payload = entry.get("raw_payload") or entry.get("vendor_payload")
    if not isinstance(payload, str):
        return payload  # type: ignore[return-value]
    parsed: dict[str, object] | list[object] | None = None
    with suppress(Exception):
        parsed = json.loads(payload)
    return parsed

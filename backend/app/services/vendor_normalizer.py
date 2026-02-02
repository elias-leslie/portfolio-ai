"""Vendor data normalization utilities."""

from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any


def normalize_vendor_row(
    row: dict[str, Any],
    *,
    vendor_name: str,
    default_symbol: str,
) -> dict[str, Any]:
    """Normalize vendor-specific row format to standard format.

    Args:
        row: Raw row data from vendor
        vendor_name: Name of the vendor source
        default_symbol: Default symbol if none found in row

    Returns:
        Normalized dictionary with standard field names
    """
    entry = dict(row)
    headline = entry.get("headline") or entry.get("title")
    summary = entry.get("summary") or entry.get("description")
    url = entry.get("url") or entry.get("link") or entry.get("article_url")
    news_source_name = entry.get("news_source_name") or entry.get("publisher")
    if isinstance(news_source_name, dict):
        news_source_name = news_source_name.get("name") or news_source_name.get("title")

    published_value = entry.get("published_at") or entry.get("published")
    published_iso = None
    if isinstance(published_value, datetime):
        published_iso = published_value.astimezone(UTC).isoformat()
    elif isinstance(published_value, str):
        published_iso = published_value
    elif isinstance(published_value, (int, float)):
        published_iso = datetime.fromtimestamp(float(published_value), tz=UTC).isoformat()

    symbol_value = entry.get("symbol") or default_symbol
    if isinstance(symbol_value, str):
        symbol_value = symbol_value.upper()

    vendor_payload = entry.get("raw_payload") or entry.get("vendor_payload")
    if isinstance(vendor_payload, str):
        with suppress(Exception):
            vendor_payload = json.loads(vendor_payload)

    normalized = {
        "headline": headline,
        "summary": summary,
        "description": summary,
        "url": url,
        "link": url,
        "source": news_source_name or vendor_name,
        "news_source_name": news_source_name or vendor_name,
        "author": entry.get("author"),
        "image_url": entry.get("image_url"),
        "published": published_iso,
        "published_at": published_iso,
        "vendor": vendor_name,
        "symbol": symbol_value or default_symbol,
    }
    if vendor_payload is not None:
        normalized["vendor_payload"] = vendor_payload

    return normalized

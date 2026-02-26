"""Vendor data normalization utilities."""

from __future__ import annotations

from ._vendor_normalizer_helpers import (
    extract_published_iso,
    extract_source_name,
    extract_symbol,
    extract_vendor_payload,
)


def normalize_vendor_row(
    row: dict[str, object],
    *,
    vendor_name: str,
    default_symbol: str,
) -> dict[str, object]:
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
    source_name = extract_source_name(entry) or vendor_name
    published_iso = extract_published_iso(entry)
    symbol = extract_symbol(entry, default_symbol)
    vendor_payload = extract_vendor_payload(entry)

    normalized: dict[str, object] = {
        "headline": headline,
        "summary": summary,
        "description": summary,
        "url": url,
        "link": url,
        "source": source_name,
        "news_source_name": source_name,
        "author": entry.get("author"),
        "image_url": entry.get("image_url"),
        "published": published_iso,
        "published_at": published_iso,
        "vendor": vendor_name,
        "symbol": symbol,
    }
    if vendor_payload is not None:
        normalized["vendor_payload"] = vendor_payload

    return normalized

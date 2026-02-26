"""Module-level helper functions for RSS feed parsing."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import time
from typing import Any, cast

from dateutil import parser as date_parser


def parse_published(entry: Any) -> dt.datetime | None:
    """Extract and normalise publication datetime from a feed entry."""
    struct_time = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct_time:
        with contextlib.suppress(Exception):
            return dt.datetime.fromtimestamp(time.mktime(struct_time), tz=dt.UTC)
    date_str = entry.get("published") or entry.get("updated")
    if not date_str:
        return None
    with contextlib.suppress(Exception):
        parsed = cast(dt.datetime, date_parser.parse(date_str))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.UTC)
        return parsed.astimezone(dt.UTC)
    return None


def extract_publisher(entry: Any, display_name: str) -> str:
    """Return publisher name from a feed entry, falling back to display_name."""
    source = entry.get("source", {})
    if isinstance(source, dict):
        name = source.get("title")
        if isinstance(name, str) and name.strip():
            return name
    publisher = entry.get("publisher")
    if isinstance(publisher, str) and publisher.strip():
        return publisher
    return display_name


def extract_image(entry: Any) -> str | None:
    """Return the first image URL from media_content or media_thumbnail."""
    media_content = entry.get("media_content") or entry.get("media_thumbnail")
    if not isinstance(media_content, list):
        return None
    for candidate in media_content:
        if isinstance(candidate, dict):
            url = candidate.get("url")
            if isinstance(url, str) and url:
                return url
    return None


def entry_to_record(
    entry: Any, symbol: str, source_name: str, display_name: str
) -> dict[str, Any] | None:
    """Convert a feedparser entry to a news record dict, or None if invalid."""
    title = (entry.get("title") or "").strip()
    link = entry.get("link") or entry.get("id") or ""
    if not title or not link:
        return None
    published_at = parse_published(entry)
    summary = entry.get("summary") or entry.get("description") or ""
    publisher = extract_publisher(entry, display_name)
    payload = {
        "title": title,
        "link": link,
        "summary": summary,
        "source": publisher,
        "published": entry.get("published"),
    }
    return {
        "symbol": symbol,
        "headline": title,
        "summary": summary,
        "url": link,
        "news_source_name": publisher,
        "author": entry.get("author"),
        "image_url": extract_image(entry),
        "published_at": published_at,
        "raw_payload": json.dumps(payload, default=str),
        "source": source_name,
    }


def in_window(record: dict[str, Any], start_utc: dt.datetime, end_utc: dt.datetime) -> bool:
    """Return True when the record's published_at is within [start_utc, end_utc]."""
    published_at = record.get("published_at")
    if not isinstance(published_at, dt.datetime):
        return True
    return start_utc <= published_at <= end_utc

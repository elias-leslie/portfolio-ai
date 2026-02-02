"""Vendor data fetching and round-robin distribution."""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ..sources.base import DATASET_NEWS, DatasetRequest
from .vendor_normalizer import normalize_vendor_row

if TYPE_CHECKING:
    from ..sources.multi_source_fetcher import MultiSourceFetcher


def fetch_vendor_entries(
    multi_source_fetcher: MultiSourceFetcher | None,
    *,
    symbol: str,
    ttl: timedelta,
    now: datetime,
    max_entries: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch entries from all configured vendors using round-robin distribution.

    Args:
        multi_source_fetcher: Fetcher instance with configured sources
        symbol: Stock symbol to fetch news for
        ttl: Time-to-live for cache
        now: Current timestamp
        max_entries: Maximum number of entries to return

    Returns:
        Tuple of (selected entries list, metadata dict with counts and errors)
    """
    metadata: dict[str, Any] = {"counts": {}, "errors": {}}
    if multi_source_fetcher is None:
        return [], metadata

    request = DatasetRequest(
        dataset=DATASET_NEWS,
        profile=None,
        symbols=[symbol],
        start=now - ttl,
        end=now,
        timezone="UTC",
    )
    dataframe, errors = multi_source_fetcher.fetch_with_fallback(request, verbose=False)
    metadata["errors"] = errors or {}

    if dataframe is None or len(dataframe) == 0:
        metadata["counts"] = {}
        return [], metadata

    vendor_counts: Counter[str] = Counter()
    vendor_buckets: dict[str, deque[dict[str, Any]]] = {}
    priority_lookup = {
        source.name: index for index, source in enumerate(multi_source_fetcher.sources)
    }

    for row in dataframe.to_dicts():
        vendor_name = str(row.get("source") or "").strip() or "unknown"
        normalized = normalize_vendor_row(
            row,
            vendor_name=vendor_name,
            default_symbol=symbol,
        )
        if not normalized.get("headline"):
            continue

        vendor_counts[vendor_name] += 1
        bucket = vendor_buckets.setdefault(vendor_name, deque())
        bucket.append(normalized)

    metadata["counts"] = dict(vendor_counts)

    if not vendor_buckets or max_entries <= 0:
        return [], metadata

    vendor_order = sorted(
        vendor_buckets.keys(),
        key=lambda name: priority_lookup.get(name, len(priority_lookup) + 1),
    )

    selected: list[dict[str, Any]] = []
    while vendor_order and len(selected) < max_entries:
        progressed = False
        for vendor_name in list(vendor_order):
            queue = vendor_buckets.get(vendor_name)
            if not queue:
                vendor_order.remove(vendor_name)
                continue

            selected.append(queue.popleft())
            progressed = True

            if not queue:
                vendor_order.remove(vendor_name)

            if len(selected) >= max_entries:
                break

        if not progressed:
            break

    return selected, metadata

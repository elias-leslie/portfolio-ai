"""Vendor data fetching and round-robin distribution."""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ..sources.base import DATASET_NEWS, DatasetRequest
from .vendor_normalizer import normalize_vendor_row

if TYPE_CHECKING:
    from ..sources.multi_source_fetcher import MultiSourceFetcher

type VendorRow = dict[str, object]


def _build_vendor_buckets(
    dataframe: object,
    symbol: str,
    priority_lookup: dict[str, int],
) -> tuple[Counter[str], dict[str, deque[VendorRow]]]:
    """Group normalized rows by vendor, preserving insertion order."""
    vendor_counts: Counter[str] = Counter()
    vendor_buckets: dict[str, deque[VendorRow]] = {}
    for row in dataframe.to_dicts():  # type: ignore[union-attr]
        vendor_name = str(row.get("source") or "").strip() or "unknown"
        normalized = normalize_vendor_row(
            row, vendor_name=vendor_name, default_symbol=symbol
        )
        if not normalized.get("headline"):
            continue
        vendor_counts[vendor_name] += 1
        vendor_buckets.setdefault(vendor_name, deque()).append(normalized)
    return vendor_counts, vendor_buckets


def _round_robin_select(
    vendor_buckets: dict[str, deque[VendorRow]],
    priority_lookup: dict[str, int],
    max_entries: int,
) -> list[VendorRow]:
    """Select entries in round-robin order by vendor priority."""
    vendor_order = sorted(
        vendor_buckets.keys(),
        key=lambda name: priority_lookup.get(name, len(priority_lookup) + 1),
    )
    selected: list[VendorRow] = []
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
    return selected


def fetch_vendor_entries(
    multi_source_fetcher: MultiSourceFetcher | None,
    *,
    symbol: str,
    ttl: timedelta,
    now: datetime,
    max_entries: int,
) -> tuple[list[VendorRow], dict[str, object]]:
    """Fetch entries from all configured vendors using round-robin distribution."""
    metadata: dict[str, object] = {"counts": {}, "errors": {}}
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
        return [], metadata

    priority_lookup = {
        source.name: index for index, source in enumerate(multi_source_fetcher.sources)
    }
    vendor_counts, vendor_buckets = _build_vendor_buckets(dataframe, symbol, priority_lookup)
    metadata["counts"] = dict(vendor_counts)

    if not vendor_buckets or max_entries <= 0:
        return [], metadata

    return _round_robin_select(vendor_buckets, priority_lookup, max_entries), metadata

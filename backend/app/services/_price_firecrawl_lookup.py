"""Firecrawl-backed fallback extraction for household vendor price quotes.

The primary price-check path is the ``household-price-scout`` Agent Hub agent.
Firecrawl is a narrow fallback for vendors whose product pages expose price,
package size, and unit price well enough to verify a quote without guessing.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict
from typing import Any

import structlog

from app.services._household_price_location import (
    firecrawl_location_terms,
    price_location_context,
)
from app.services._price_vendor_adapters import (
    VendorAdapter,
    VendorQuote,
    VendorResult,
    _extract_json_object,
    _looks_blocked,
)
from app.utils import safe_subprocess

logger = structlog.get_logger(__name__)

FIRECRAWL_TIMEOUT_SECONDS = 30
FIRECRAWL_SEARCH_LIMIT = 2
FIRECRAWL_VENDOR_PRODUCT_CAP = 4

_FIRECRAWL_SITES: dict[str, tuple[str, ...]] = {
    "amazon": ("amazon.com",),
    "walmart": ("walmart.com",),
    "aldi": ("aldi.us",),
    "costco": ("costco.com", "sameday.costco.com"),
    "publix": ("publix.com",),
}

_MONEY_PATTERN = re.compile(r"(?:USD\s*)?\$\s*(?P<amount>\d+(?:\.\d{1,2})?)", flags=re.I)
_LOOSE_PRICE_PATTERN = re.compile(r"\b(?P<amount>\d+(?:\.\d{1,2})?)\b")
_CENTS_PATTERN = re.compile(r"(?P<amount>\d+(?:\.\d+)?)\s*(?:¢|cents?)", flags=re.I)


def lookup_vendor_prices_with_firecrawl(
    adapter: VendorAdapter,
    products: list[dict[str, Any]],
) -> VendorResult:
    """Search/scrape a small batch of products with Firecrawl CLI.

    A subprocess timeout is intentional: this path performs network I/O through
    an external CLI and must not leave the Hatchet worker stuck on a hung scrape.
    """

    sites = _FIRECRAWL_SITES.get(adapter.vendor_key)
    if not sites:
        return VendorResult(
            vendor_key=adapter.vendor_key,
            status="error",
            error="Firecrawl fallback is not configured for this vendor.",
        )

    quotes: list[VendorQuote] = []
    errors: list[str] = []
    for product in products[:FIRECRAWL_VENDOR_PRODUCT_CAP]:
        try:
            quote = _lookup_product(adapter, product, sites)
        except FileNotFoundError:
            return VendorResult(
                vendor_key=adapter.vendor_key,
                status="error",
                error="Firecrawl CLI is not installed on this host.",
            )
        except subprocess.TimeoutExpired:
            errors.append(f"{product.get('name')}: Firecrawl timed out")
            continue
        except Exception as exc:  # defensive: vendor failure must stay isolated
            logger.info(
                "firecrawl_price_lookup_error",
                vendor_key=adapter.vendor_key,
                product_id=product.get("id"),
                error=str(exc),
            )
            errors.append(f"{product.get('name')}: {exc}")
            continue
        if quote is not None:
            quotes.append(quote)

    if quotes:
        return VendorResult(
            vendor_key=adapter.vendor_key,
            status="ok" if len(quotes) == len(products) else "partial",
            quotes=quotes,
            error="; ".join(errors[:2]) or None,
        )
    return VendorResult(
        vendor_key=adapter.vendor_key,
        status="error",
        error="; ".join(errors[:2])
        or "Firecrawl could not verify price, package size, and unit price.",
    )


def _lookup_product(
    adapter: VendorAdapter,
    product: dict[str, Any],
    sites: tuple[str, ...],
) -> VendorQuote | None:
    for site in sites:
        query = _search_query(adapter, product, site)
        search_results = _firecrawl_search(query)
        for result in search_results[:FIRECRAWL_SEARCH_LIMIT]:
            quote = _quote_from_scrape(adapter, product, result)
            if quote is not None:
                return quote
    return None


def _search_query(adapter: VendorAdapter, product: dict[str, Any], site: str) -> str:
    parts = [
        str(product.get("brand") or "").strip(),
        str(product.get("name") or "").strip(),
        str(product.get("package") or "").strip(),
    ]
    product_text = " ".join(part for part in parts if part)
    location = firecrawl_location_terms(adapter.vendor_key)
    return (
        f"site:{site} {adapter.display_name} {product_text} {location} "
        "price package unit price"
    )


def _firecrawl_search(query: str) -> list[dict[str, Any]]:
    completed = safe_subprocess.run(
        ["firecrawl", "search", query, "--limit", str(FIRECRAWL_SEARCH_LIMIT), "--json"],
        capture_output=True,
        text=True,
        timeout=FIRECRAWL_TIMEOUT_SECONDS,
    )
    content = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        if _looks_blocked(content):
            return []
        raise RuntimeError(content.strip() or "Firecrawl search failed.")
    payload = json.loads(completed.stdout or "{}")
    web_results = ((payload.get("data") or {}).get("web") or []) if isinstance(payload, dict) else []
    return [result for result in web_results if isinstance(result, dict) and result.get("url")]


def _quote_from_scrape(
    adapter: VendorAdapter,
    product: dict[str, Any],
    search_result: dict[str, Any],
) -> VendorQuote | None:
    url = str(search_result.get("url") or "")
    if not url:
        return None
    completed = safe_subprocess.run(
        [
            "firecrawl",
            "scrape",
            url,
            "--only-main-content",
            "-Q",
            (
                "Return JSON only with product_title, price, package_size, "
                "unit_price, availability, membership_required from this product page. "
                f"{price_location_context(adapter.vendor_key)}"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=FIRECRAWL_TIMEOUT_SECONDS,
    )
    content = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0 or _looks_blocked(content):
        return None
    try:
        payload = _extract_json_object(completed.stdout or "")
    except (ValueError, json.JSONDecodeError):
        return None
    return _quote_from_payload(adapter, product, payload, url=url, fallback_title=search_result.get("title"))


def _quote_from_payload(
    adapter: VendorAdapter,
    product: dict[str, Any],
    payload: dict[str, Any],
    *,
    url: str,
    fallback_title: Any,
    confidence: float = 0.72,
) -> VendorQuote | None:
    price = _parse_money(payload.get("price"))
    package_label = str(payload.get("package_size") or "").strip() or None
    title = str(payload.get("product_title") or fallback_title or "").strip()
    if price is None or price <= 0 or not package_label or not title:
        return None
    unit_price = _parse_unit_price(payload.get("unit_price"))
    membership_required = _parse_bool(payload.get("membership_required")) or adapter.vendor_key == "costco"
    availability = str(payload.get("availability") or "").strip() or None
    return VendorQuote(
        product_id=str(product["id"]),
        title=title,
        price=round(price, 2),
        url=url or None,
        package_label=package_label,
        unit_price=unit_price,
        availability=availability,
        promo_text="Firecrawl verified page extraction",
        membership_required=membership_required,
        confidence=confidence,
        quote_kind="exact_or_nearest",
    )


def _parse_money(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    text = str(value or "")
    match = _MONEY_PATTERN.search(text)
    if match is None:
        match = _LOOSE_PRICE_PATTERN.search(text)
    if match is None:
        return None
    try:
        return float(match.group("amount"))
    except ValueError:
        return None


def _parse_unit_price(value: Any) -> float | None:
    if isinstance(value, int | float):
        return round(float(value), 4)
    text = str(value or "")
    cents = _CENTS_PATTERN.search(text)
    if cents is not None:
        try:
            return round(float(cents.group("amount")) / 100, 4)
        except ValueError:
            return None
    parsed = _parse_money(text)
    return round(parsed, 4) if parsed is not None else None


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "member", "membership"}


def vendor_result_to_json(result: VendorResult) -> str:
    """Compact audit string for Agent Hub run messages."""

    return json.dumps(
        {
            "status": result.status,
            "quotes": [asdict(quote) for quote in result.quotes],
            "error": result.error,
        },
        default=str,
    )


__all__ = ["lookup_vendor_prices_with_firecrawl", "vendor_result_to_json"]

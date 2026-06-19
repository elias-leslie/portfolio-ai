"""Web-backed fallback extraction for household vendor price quotes.

The primary price-check path is the ``household-price-scout`` Agent Hub agent.
This module first tries Firecrawl when available, then falls back to the shared
``st web`` search/fetch stack. Both paths only emit a quote when the page (not
just the search snippet) exposes price and package size well enough to verify a
unit-basis comparison without guessing.
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
from app.services._household_report_builder import _extract_package_measure
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
ST_WEB_TIMEOUT_SECONDS = 25
ST_WEB_SEARCH_LIMIT = 3
ST_WEB_MAX_CHARS = 1800
ST_WEB_FOCUS_QUERY = (
    "product title current price one-time price package size unit price "
    "ounce ounces oz fluid ounce fl oz pound lb count ct availability"
)

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
_UNIT_PRICE_PATTERN = re.compile(
    r"(?:USD\s*)?\$?\s*(?P<amount>\d+(?:\.\d{1,4})?)\s*/\s*"
    r"(?:fl\s*oz|fluid ounces?|ounces?|oz|lb|pounds?|count|ct)",
    flags=re.I,
)
_PRICE_PATTERNS = (
    re.compile(
        r"one-time\s+purchase\s*[:.]?\s*(?:USD\s*)?\$\s*(?P<amount>\d+(?:\.\d{1,2})?)",
        flags=re.I,
    ),
    re.compile(
        r"current\s+price(?:\s+is)?\s*[:]?\s*(?:USD\s*)?\$?\s*(?P<amount>\d+(?:\.\d{1,2})?)",
        flags=re.I,
    ),
    re.compile(
        r"\bprice\s*[:]\s*(?:USD\s*)?\$?\s*(?P<amount>\d+(?:\.\d{1,2})?)",
        flags=re.I,
    ),
)
_STOP_TERMS = {
    "and",
    "for",
    "the",
    "with",
    "pack",
    "of",
    "fl",
    "oz",
    "ounce",
    "ounces",
    "fluid",
    "lb",
    "pound",
    "pounds",
    "ct",
    "count",
}


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
    errors: list[str] = []
    for site in sites:
        query = _search_query(adapter, product, site)
        try:
            search_results = _firecrawl_search(query)
        except FileNotFoundError:
            errors.append("Firecrawl CLI is not installed on this host.")
            break
        except subprocess.TimeoutExpired:
            errors.append("Firecrawl timed out")
            continue
        except Exception as exc:
            errors.append(str(exc))
            continue
        for result in search_results[:FIRECRAWL_SEARCH_LIMIT]:
            try:
                quote = _quote_from_scrape(adapter, product, result)
            except subprocess.TimeoutExpired:
                errors.append("Firecrawl timed out")
                continue
            if quote is not None:
                return quote
    for site in sites:
        try:
            quote = _lookup_product_with_st_web(adapter, product, site)
        except FileNotFoundError:
            errors.append("st web CLI is not installed on this host.")
            break
        except subprocess.TimeoutExpired:
            errors.append("st web timed out")
            continue
        except Exception as exc:
            errors.append(str(exc))
            continue
        if quote is not None:
            return quote
    if errors:
        raise RuntimeError("; ".join(dict.fromkeys(errors[:3])))
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


def _equivalent_search_query(adapter: VendorAdapter, product: dict[str, Any], site: str) -> str:
    product_text = _generic_product_text(product)
    location = firecrawl_location_terms(adapter.vendor_key)
    return (
        f"site:{site} {adapter.display_name} {product_text} {location} "
        "current price package unit price equivalent store brand"
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


def _lookup_product_with_st_web(
    adapter: VendorAdapter,
    product: dict[str, Any],
    site: str,
) -> VendorQuote | None:
    queries = [
        (_search_query(adapter, product, site), False),
        (_equivalent_search_query(adapter, product, site), True),
    ]
    seen_urls: set[str] = set()
    for query, equivalent in queries:
        for result in _st_web_search(query):
            url = str(result.get("url") or "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if not _is_product_url(adapter.vendor_key, url):
                continue
            if not _result_matches_product(product, result, equivalent=equivalent):
                continue
            quote = _quote_from_st_web_fetch(
                adapter,
                product,
                result,
                equivalent=equivalent,
            )
            if quote is not None:
                return quote
    return None


def _st_web_search(query: str) -> list[dict[str, Any]]:
    completed = safe_subprocess.run(
        [
            "st",
            "web",
            "search",
            "--query",
            query,
            "--limit",
            str(ST_WEB_SEARCH_LIMIT),
            "--raw",
        ],
        capture_output=True,
        text=True,
        timeout=ST_WEB_TIMEOUT_SECONDS,
    )
    content = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError(content.strip() or "st web search failed.")
    payload = json.loads(completed.stdout or "{}")
    raw_results = payload.get("results") if isinstance(payload, dict) else []
    return [result for result in raw_results or [] if isinstance(result, dict) and result.get("url")]


def _quote_from_st_web_fetch(  # noqa: PLR0911
    adapter: VendorAdapter,
    product: dict[str, Any],
    search_result: dict[str, Any],
    *,
    equivalent: bool,
) -> VendorQuote | None:
    url = str(search_result.get("url") or "")
    completed = safe_subprocess.run(
        [
            "st",
            "web",
            "fetch",
            "--url",
            url,
            "--focus-query",
            ST_WEB_FOCUS_QUERY,
            "--max-chars",
            str(ST_WEB_MAX_CHARS),
            "--raw",
        ],
        capture_output=True,
        text=True,
        timeout=ST_WEB_TIMEOUT_SECONDS,
    )
    content = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0 or _looks_blocked(content):
        return None
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_title = str(
        payload.get("title")
        or payload.get("site_name")
        or ""
    ).strip()
    search_title = str(search_result.get("title") or "").strip()
    title = (
        raw_title
        if raw_title
        and _result_matches_product(product, {"title": raw_title}, equivalent=equivalent)
        else search_title
    )
    body = str(payload.get("content") or "")
    title_text = "\n".join(
        part
        for part in (
            title,
            search_title,
            str(search_result.get("snippet") or ""),
        )
        if part
    )
    text = "\n".join(
        part
        for part in (
            title,
            search_title,
            str(search_result.get("snippet") or ""),
            body,
        )
        if part
    )
    price = _parse_contextual_price(text)
    measure = _quote_measure(
        product,
        title_text,
        text,
    )
    if price is None or price <= 0 or measure is None:
        return None
    if not _package_reasonable_for_product(product, measure):
        return None
    availability = _parse_availability(text)
    if availability == "out of stock":
        return None
    confidence = _match_confidence(product, title_text or text, equivalent=equivalent)
    if confidence < 0.7:
        return None
    return VendorQuote(
        product_id=str(product["id"]),
        title=title or str(search_result.get("title") or "").strip(),
        price=round(price, 2),
        url=url or None,
        package_label=measure.display_label,
        unit_price=_parse_page_unit_price(text),
        availability=availability,
        promo_text=(
            "st web verified equivalent unit-basis page"
            if equivalent
            else "st web verified page extraction"
        ),
        membership_required=adapter.vendor_key == "costco" or "membership" in text.lower(),
        confidence=confidence,
        quote_kind="equivalent_unit_basis" if equivalent else "exact_or_nearest",
    )


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


def _parse_contextual_price(text: str) -> float | None:
    """Prefer current/one-time page prices over list prices or review prose."""
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            try:
                return float(match.group("amount"))
            except ValueError:
                return None
    # Common product-page shape: "$38.79 68 fl oz" or "$21.48 ; How you'll get".
    match = re.search(
        r"(?:^|[\s|•])(?:USD\s*)?\$\s*(?P<amount>\d+(?:\.\d{1,2})?)"
        r"(?=\s*(?:\d+(?:\.\d+)?\s*(?:fl\s*oz|fluid ounces?|ounces?|oz|lb|pounds?|count|ct)|[;•]|How|$))",
        text,
        flags=re.I,
    )
    if match is not None:
        try:
            return float(match.group("amount"))
        except ValueError:
            return None
    return _parse_money(text)


def _parse_availability(text: str) -> str | None:
    lowered = text.lower()
    if "out of stock" in lowered:
        return "out of stock"
    if "in stock" in lowered:
        return "in stock"
    if "pickup" in lowered and "delivery" in lowered:
        return "pickup or delivery"
    if "delivery" in lowered:
        return "delivery"
    if "pickup" in lowered:
        return "pickup"
    return None


def _is_product_url(vendor_key: str, url: str) -> bool:
    lowered = url.lower()
    if vendor_key == "amazon":
        return "/dp/" in lowered or "/gp/product/" in lowered
    if vendor_key == "walmart":
        return "/ip/" in lowered
    if vendor_key == "publix":
        return "/products/" in lowered or "product_id=" in lowered
    if vendor_key == "costco":
        return "/p/" in lowered or "/products/" in lowered
    if vendor_key == "aldi":
        return "/products/" in lowered or "/product/" in lowered
    return True


def _quote_measure(product: dict[str, Any], title_text: str, full_text: str) -> Any:
    title_measure = _extract_package_measure(
        title_text,
        {"Product Name": title_text},
    )
    if title_measure is not None:
        return title_measure
    full_measure = _extract_package_measure(full_text, {"Product Name": full_text[:200]})
    if full_measure is not None:
        return full_measure
    return _extract_package_measure(
        str(product.get("package") or ""),
        {"Product Name": str(product.get("package") or "")},
    )


def _package_reasonable_for_product(product: dict[str, Any], quote_measure: Any) -> bool:
    baseline_quantity = product.get("baseline_package_quantity")
    baseline_unit = str(product.get("baseline_package_unit") or "").strip()
    if baseline_quantity is None:
        baseline = _extract_package_measure(
            str(product.get("package") or ""),
            {"Product Name": str(product.get("package") or "")},
        )
        if baseline is None:
            return True
        baseline_quantity = baseline.normalized_quantity
        baseline_unit = baseline.normalized_unit
    try:
        baseline_value = float(baseline_quantity)
    except (TypeError, ValueError):
        return True
    if baseline_value <= 0 or not baseline_unit:
        return True
    if quote_measure.normalized_unit != baseline_unit:
        return True
    ratio = float(quote_measure.normalized_quantity) / baseline_value
    return 0.15 <= ratio <= 4.0


def _generic_product_text(product: dict[str, Any]) -> str:
    name = str(product.get("name") or "").strip()
    brand = str(product.get("brand") or "").strip()
    package = str(product.get("package") or "").strip()
    generic = name
    if brand:
        generic = re.sub(re.escape(brand), " ", generic, flags=re.I)
    generic = re.sub(r"\s+", " ", generic).strip() or name
    return " ".join(part for part in (generic, package) if part)


def _meaningful_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9]+", text.lower())
        if token not in _STOP_TERMS and len(token) > 2
    }


def _result_matches_product(
    product: dict[str, Any],
    search_result: dict[str, Any],
    *,
    equivalent: bool,
) -> bool:
    haystack = " ".join(
        str(search_result.get(key) or "")
        for key in ("title", "snippet", "url")
    )
    name_terms = _meaningful_terms(_generic_product_text(product))
    if not name_terms:
        return True
    hits = name_terms & _meaningful_terms(haystack)
    if equivalent:
        return len(hits) >= min(2, len(name_terms))
    brand = str(product.get("brand") or "").strip().lower()
    if brand and brand not in haystack.lower():
        return len(hits) >= min(3, len(name_terms))
    return len(hits) >= min(2, len(name_terms))


def _match_confidence(
    product: dict[str, Any],
    title: str,
    *,
    equivalent: bool,
) -> float:
    brand = str(product.get("brand") or "").strip().lower()
    title_lower = title.lower()
    terms = _meaningful_terms(_generic_product_text(product))
    hits = terms & _meaningful_terms(title)
    if brand and brand in title_lower:
        return 0.84 if not equivalent else 0.76
    if terms and len(hits) >= min(3, len(terms)):
        return 0.76 if not equivalent else 0.72
    if equivalent and terms and len(hits) >= min(2, len(terms)):
        return 0.7
    return 0.62


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
    unit_price = _UNIT_PRICE_PATTERN.search(text)
    if unit_price is not None:
        try:
            return round(float(unit_price.group("amount")), 4)
        except ValueError:
            return None
    cents = _CENTS_PATTERN.search(text)
    if cents is not None:
        try:
            return round(float(cents.group("amount")) / 100, 4)
        except ValueError:
            return None
    parsed = _parse_money(text)
    return round(parsed, 4) if parsed is not None else None


def _parse_page_unit_price(text: str) -> float | None:
    unit_price = _UNIT_PRICE_PATTERN.search(text)
    if unit_price is not None:
        try:
            return round(float(unit_price.group("amount")), 4)
        except ValueError:
            return None
    cents = _CENTS_PATTERN.search(text)
    if cents is not None:
        try:
            return round(float(cents.group("amount")) / 100, 4)
        except ValueError:
            return None
    return None


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

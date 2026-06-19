"""Unit tests for Firecrawl fallback price extraction."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from app.services._price_firecrawl_lookup import lookup_vendor_prices_with_firecrawl
from app.services._price_vendor_adapters import VENDOR_ADAPTERS

_WALMART = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "walmart")
_ALDI = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "aldi")

_PRODUCTS = [
    {"id": "p-1", "name": "GV EDAMAME", "brand": None, "package": None, "last_paid": 1.92},
]


def _completed(args: list[str], stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr="")


def test_firecrawl_lookup_parses_fenced_scrape_json() -> None:
    search = (
        '{"success":true,"data":{"web":[{"url":"https://www.walmart.com/ip/328567678",'
        '"title":"Great Value Edamame, 12 oz (Frozen) - Walmart.com",'
        '"description":"Great Value Frozen Edamame 12 oz"}]}}'
    )
    scrape = (
        "Scrape ID: 123\n```json\n"
        '{"product_title":"Great Value Edamame, 12 oz (Frozen)",'
        '"price":"$1.92","package_size":"12 oz","unit_price":"16.0 ¢/oz",'
        '"availability":"Pickup or delivery","membership_required":false}'
        "\n```"
    )

    with patch(
        "app.services._price_firecrawl_lookup.safe_subprocess.run",
        side_effect=[
            _completed(["firecrawl", "search"], search),
            _completed(["firecrawl", "scrape"], scrape),
        ],
    ) as run:
        result = lookup_vendor_prices_with_firecrawl(_WALMART, _PRODUCTS)

    assert result.status == "ok"
    assert len(result.quotes) == 1
    quote = result.quotes[0]
    assert quote.product_id == "p-1"
    assert quote.price == 1.92
    assert quote.package_label == "12 oz"
    assert quote.unit_price == 0.16
    assert quote.confidence == 0.72
    assert run.call_count == 2


def test_firecrawl_search_snippet_prefers_current_price_not_unit_price() -> None:
    search = (
        '{"success":true,"data":{"web":[{"url":"https://www.aldi.us/store/aldi/products/1",'
        '"title":"Simply Nature Organic Extra Virgin Olive Oil - Aldi",'
        '"description":"16.9 fl oz • $0.47/fl oz • Current price: $7.99$7.99"}]}}'
    )

    with patch(
        "app.services._price_firecrawl_lookup.safe_subprocess.run",
        side_effect=[
            _completed(["firecrawl", "search"], search),
            _completed(["firecrawl", "scrape"], "no json here"),
        ],
    ):
        result = lookup_vendor_prices_with_firecrawl(_ALDI, _PRODUCTS)

    assert result.status == "ok"
    quote = result.quotes[0]
    assert quote.price == 7.99
    assert quote.package_label == "16.9 fl oz"
    assert quote.unit_price is None
    assert quote.confidence == 0.58


def test_firecrawl_lookup_reports_missing_cli() -> None:
    with patch(
        "app.services._price_firecrawl_lookup.safe_subprocess.run",
        side_effect=FileNotFoundError("firecrawl"),
    ):
        result = lookup_vendor_prices_with_firecrawl(_WALMART, _PRODUCTS)

    assert result.status == "error"
    assert "not installed" in (result.error or "")

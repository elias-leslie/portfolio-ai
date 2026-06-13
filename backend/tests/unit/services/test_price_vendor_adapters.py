"""Unit tests for the price-check vendor adapters (prompt + parse)."""

from __future__ import annotations

import json

from app.services._price_vendor_adapters import VENDOR_ADAPTERS, VendorAdapter

_AMAZON = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "amazon")

_PRODUCTS = [
    {"id": "p-1", "name": "GV Edamame", "brand": "Great Value", "package": "12 oz", "last_paid": 2.48},
    {"id": "p-2", "name": "Olive Oil", "brand": None, "package": None, "last_paid": 8.99},
]


def test_registry_covers_the_three_vendors() -> None:
    assert [a.vendor_key for a in VENDOR_ADAPTERS] == ["amazon", "walmart", "publix"]


def test_build_prompt_carries_products_and_vendor_guidance() -> None:
    prompt = _AMAZON.build_prompt(_PRODUCTS)
    assert "amazon.com" in prompt
    assert '"product_id": "p-1"' in prompt
    assert "GV Edamame" in prompt
    assert "lower unit-price comparable substitute" in prompt
    assert '"status": "ok" | "partial" | "blocked"' in prompt


def test_parse_ok_response_keeps_valid_quotes_and_drops_garbage() -> None:
    content = json.dumps(
        {
            "status": "ok",
            "quotes": [
                {"product_id": "p-1", "title": "Edamame 12oz", "price": 2.12,
                 "url": "https://a.co/x", "package_label": "12 oz",
                 "unit_price": 0.18, "promo_text": "Rollback",
                 "membership_required": True, "confidence": 0.9,
                 "quote_kind": "weekly_ad_promo"},
                {"product_id": "p-2", "title": "No price here"},
                {"product_id": "", "title": "Missing id", "price": 4.0},
                {"product_id": "p-2", "title": "Absurd", "price": 99999.0},
            ],
            "notes": "",
        }
    )
    result = _AMAZON.parse_response(content)
    assert result.status == "ok"
    assert len(result.quotes) == 1
    quote = result.quotes[0]
    assert (quote.product_id, quote.price, quote.unit_price) == ("p-1", 2.12, 0.18)
    assert quote.promo_text == "Rollback"
    assert quote.membership_required is True
    assert quote.quote_kind == "weekly_ad_promo"


def test_parse_tolerates_code_fences_and_leading_prose() -> None:
    content = (
        "Here are the results:\n```json\n"
        '{"status": "ok", "quotes": [{"product_id": "p-1", "title": "X", "price": 3.5}]}'
        "\n```"
    )
    result = _AMAZON.parse_response(content)
    assert result.status == "ok"
    assert result.quotes[0].price == 3.5


def test_explicit_blocked_status_reports_blocked() -> None:
    result = _AMAZON.parse_response('{"status": "blocked", "quotes": [], "notes": "robot wall"}')
    assert result.status == "blocked"
    assert result.quotes == []
    assert "robot wall" in (result.error or "")


def test_partial_status_is_preserved_with_quotes() -> None:
    result = _AMAZON.parse_response(
        '{"status": "partial", "quotes": [{"product_id": "p-1", "title": "X", "price": 3.5}]}'
    )
    assert result.status == "partial"
    assert result.quotes[0].price == 3.5


def test_captcha_prose_without_json_reports_blocked_not_error() -> None:
    result = _AMAZON.parse_response("The page demanded I solve a CAPTCHA to continue.")
    assert result.status == "blocked"


def test_non_json_reply_reports_error() -> None:
    result = _AMAZON.parse_response("I could not find anything useful.")
    assert result.status == "error"
    assert result.error is not None


def test_adapter_is_vendor_agnostic_in_parsing() -> None:
    publix = next(a for a in VENDOR_ADAPTERS if a.vendor_key == "publix")
    assert isinstance(publix, VendorAdapter)
    result = publix.parse_response(
        '{"status": "ok", "quotes": [{"product_id": "p-1", "title": "BOGO", "price": 1.99}]}'
    )
    assert result.vendor_key == "publix"
    assert result.quotes[0].price == 1.99

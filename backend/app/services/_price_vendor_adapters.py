"""Vendor adapters for the cross-vendor price check (phase 3).

Each adapter builds the per-vendor research prompt for the
``household-price-scout`` Agent Hub agent (which runs search_web /
fetch_web_page server-side, with browser-rendered fallback) and parses the
agent's JSON reply into normalized quotes. Vendors differ only in how to find
a price (Amazon/Walmart product search vs the Publix weekly ad), so the
adapter carries vendor-specific guidance text; parsing is shared.

Blocked/captcha handling: the agent is instructed to report
``status: "blocked"`` when a vendor serves bot walls instead of results; a
parse failure or an explicit blocked status downgrades that vendor for the
run without failing the others.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_PRICE_RANGE_OK = (0.01, 10_000.0)


@dataclass(frozen=True)
class VendorQuote:
    product_id: str
    title: str
    price: float
    url: str | None = None
    package_label: str | None = None
    unit_price: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class VendorResult:
    vendor_key: str
    status: str  # ok | blocked | error
    quotes: list[VendorQuote] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class VendorAdapter:
    vendor_key: str
    display_name: str
    merchant_name: str
    guidance: str

    def build_prompt(self, products: list[dict[str, Any]]) -> str:
        """One agent call per vendor: search every product, answer in JSON."""
        product_lines = json.dumps(
            [
                {
                    "product_id": str(p["id"]),
                    "name": p["name"],
                    "brand": p.get("brand"),
                    "package": p.get("package"),
                    "last_paid": p.get("last_paid"),
                }
                for p in products
            ],
            default=str,
        )
        return (
            f"Vendor: {self.display_name}\n{self.guidance}\n\n"
            f"Products to price:\n{product_lines}\n\n"
            "For each product, find the current price for the closest matching "
            "item (same brand and package size when possible). Use search_web "
            "and fetch_web_page. If the vendor blocks you (captcha, robot "
            'check, empty bot-walled pages), stop and report status "blocked".\n\n'
            "Respond with ONLY this JSON object:\n"
            "{\n"
            '  "status": "ok" | "blocked",\n'
            '  "quotes": [\n'
            "    {\n"
            '      "product_id": "<id from the input list>",\n'
            '      "title": "<matched item title>",\n'
            '      "price": <current price in dollars>,\n'
            '      "url": "<product page url>",\n'
            '      "package_label": "<package size text or null>",\n'
            '      "unit_price": <price per unit or null>,\n'
            '      "confidence": <0.0-1.0 match confidence>\n'
            "    }\n"
            "  ],\n"
            '  "notes": "<short notes, e.g. which products had no match>"\n'
            "}\n"
            "Omit products you could not confidently match — never guess a price."
        )

    def parse_response(self, content: str) -> VendorResult:
        try:
            payload = _extract_json_object(content)
        except ValueError as exc:
            if _looks_blocked(content):
                return VendorResult(
                    vendor_key=self.vendor_key,
                    status="blocked",
                    error="Vendor blocked automated access.",
                )
            return VendorResult(vendor_key=self.vendor_key, status="error", error=str(exc))
        status = str(payload.get("status") or "ok").strip().lower()
        if status == "blocked" or _looks_blocked(content):
            return VendorResult(
                vendor_key=self.vendor_key,
                status="blocked",
                error=str(payload.get("notes") or "Vendor blocked automated access."),
            )
        quotes = []
        for raw in payload.get("quotes") or []:
            quote = _parse_quote(raw)
            if quote is not None:
                quotes.append(quote)
        return VendorResult(vendor_key=self.vendor_key, status="ok", quotes=quotes)


def _parse_quote(raw: Any) -> VendorQuote | None:
    if not isinstance(raw, dict):
        return None
    product_id = str(raw.get("product_id") or "").strip()
    title = str(raw.get("title") or "").strip()
    try:
        price = float(raw.get("price"))
    except (TypeError, ValueError):
        return None
    if not product_id or not title:
        return None
    if not (_PRICE_RANGE_OK[0] <= price <= _PRICE_RANGE_OK[1]):
        return None
    unit_price = raw.get("unit_price")
    confidence = raw.get("confidence")
    return VendorQuote(
        product_id=product_id,
        title=title,
        price=round(price, 2),
        url=str(raw["url"]) if raw.get("url") else None,
        package_label=str(raw["package_label"]) if raw.get("package_label") else None,
        unit_price=float(unit_price) if unit_price is not None else None,
        confidence=float(confidence) if confidence is not None else None,
    )


_BLOCKED_MARKERS = (
    "captcha",
    "robot check",
    "are you a robot",
    "access denied",
    "verify you are human",
)


def _looks_blocked(content: str) -> bool:
    lowered = content.lower()
    return any(marker in lowered for marker in _BLOCKED_MARKERS)


def _extract_json_object(content: str) -> dict[str, Any]:
    """Parse the agent's JSON answer, tolerating code fences / leading prose."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match is None:
            raise ValueError("Price scout returned no JSON object.") from None
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Price scout returned non-object JSON.")
    return parsed


VENDOR_ADAPTERS: tuple[VendorAdapter, ...] = (
    VendorAdapter(
        vendor_key="amazon",
        display_name="Amazon",
        merchant_name="Amazon",
        guidance=(
            "Search amazon.com product listings (e.g. "
            "https://www.amazon.com/s?k=<query>). Prefer the exact brand and "
            "package size; use the listed price, not subscribe-and-save."
        ),
    ),
    VendorAdapter(
        vendor_key="walmart",
        display_name="Walmart",
        merchant_name="Walmart",
        guidance=(
            "Search walmart.com product listings (e.g. "
            "https://www.walmart.com/search?q=<query>). Use the online price "
            "for the closest brand/package match."
        ),
    ),
    VendorAdapter(
        vendor_key="publix",
        display_name="Publix",
        merchant_name="Publix",
        guidance=(
            "Check the Publix weekly ad and product pages "
            "(https://www.publix.com/savings/weekly-ad and publix.com search). "
            "Weekly-ad promo prices count; note BOGO as half the regular price "
            "in unit terms only when the regular price is shown."
        ),
    ),
)

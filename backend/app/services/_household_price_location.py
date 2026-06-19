"""Household store-location hints for local grocery price research."""

from __future__ import annotations

import os

DEFAULT_HOUSEHOLD_POSTAL_CODE = os.getenv("HOUSEHOLD_PRICE_POSTAL_CODE", "33770")

_DEFAULT_VENDOR_LOCATION_HINTS: dict[str, str] = {
    "amazon": "Deliver to ZIP 33770; no local store preference.",
    "walmart": "Prefer Largo, FL Walmart pickup/delivery pricing near ZIP 33770.",
    "aldi": "Prefer Largo, FL ALDI pickup/delivery pricing near ZIP 33770.",
    "publix": "Prefer Largo, FL Publix pickup/delivery pricing near ZIP 33770.",
    "costco": "Prefer the Costco Clearwater warehouse/store; use ZIP 33770 when prompted.",
}


def vendor_location_hint(vendor_key: str) -> str:
    env_key = f"HOUSEHOLD_PRICE_{vendor_key.upper()}_LOCATION_HINT"
    configured = os.getenv(env_key)
    if configured:
        return configured.strip()
    return _DEFAULT_VENDOR_LOCATION_HINTS.get(
        vendor_key,
        f"Use local pricing for ZIP {DEFAULT_HOUSEHOLD_POSTAL_CODE}.",
    )


def price_location_context(vendor_key: str) -> str:
    return (
        f"Local price context: ZIP code {DEFAULT_HOUSEHOLD_POSTAL_CODE}. "
        f"{vendor_location_hint(vendor_key)} If the page requires a ZIP, "
        "store, pickup, or delivery location before showing price, use this "
        "local context. Never guess a local price when the retailer still hides it."
    )


def firecrawl_location_terms(vendor_key: str) -> str:
    hint = vendor_location_hint(vendor_key)
    return f"{DEFAULT_HOUSEHOLD_POSTAL_CODE} {hint}"


__all__ = [
    "DEFAULT_HOUSEHOLD_POSTAL_CODE",
    "firecrawl_location_terms",
    "price_location_context",
    "vendor_location_hint",
]

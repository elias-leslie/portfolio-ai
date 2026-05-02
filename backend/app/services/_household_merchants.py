"""Merchant normalization and household transaction classification helpers."""

from __future__ import annotations

import re
from typing import Any

from app.services._household_report_builder import _merchant_root

MIN_SUBSCRIPTION_AMOUNT = 5.0
MAX_SUBSCRIPTION_AMOUNT = 25.0
BILLS_AMOUNT_THRESHOLD = 800.0


def _canonical_merchant_name(raw_merchant: str) -> str:
    root = _merchant_root(raw_merchant)
    if not root:
        return raw_merchant.strip() or "Unknown merchant"
    collapsed = root.replace(" ", "")
    if "walmart" in collapsed or "wmsupercenter" in collapsed:
        store_match = re.search(r"#\s?(\d{4})", raw_merchant)
        location_match = re.search(
            r"(LARGO|CLEARWATER|BELLEAIR BLUF|BELLEAIR BLF)\s+FL",
            raw_merchant,
            flags=re.IGNORECASE,
        )
        store_suffix = f" (Store #{store_match.group(1)})" if store_match else ""
        location_suffix = f", {location_match.group(1).title()}, FL" if location_match else ""
        return f"Walmart{store_suffix}{location_suffix}"
    if "amazon" in collapsed or "amzn" in collapsed:
        return "Amazon"
    if "wholefoods" in collapsed:
        return "Whole Foods"
    return re.sub(r"\s+", " ", raw_merchant).strip()


def _classify_statement_flow(description: str) -> str:
    normalized = description.lower()
    if "payment thank you" in normalized or normalized.startswith("payment"):
        return "payment"
    if "refund" in normalized or "return" in normalized:
        return "refund"
    return "expense"


def _classify_wells_flow(description: str) -> str:
    normalized = description.lower()
    if (
        "payroll" in normalized
        or "deposit" in normalized
        or "ui benefit" in normalized
        or "payables" in normalized
        or "salary" in normalized
    ):
        return "income"
    if "transfer from" in normalized or "zelle from" in normalized:
        return "transfer_in"
    if (
        "transfer to" in normalized
        or "zelle to" in normalized
        or "credit crd epay" in normalized
        or "cepay" in normalized
        or "inst xfer" in normalized
        or "moneyline" in normalized
        or "atm withdrawal" in normalized
        or "online transfer" in normalized
        or "recurring transfer" in normalized
    ):
        return "transfer_out"
    return "expense"


def _classify_merchant(
    *, raw_merchant: str, description: str, amount: float | None = None
) -> tuple[str, str]:
    normalized = _merchant_root(f"{raw_merchant} {description}")
    rules = [
        (["payroll", "ui benefit", "payables", "salary", "wages"], ("Income", "essential")),
        (["zelle from", "transfer from"], ("Transfers", "mixed")),
        (
            [
                "credit crd epay",
                "payment thank you",
                "inst xfer",
                "online transfer",
                "recurring transfer",
                "moneyline",
                "zelle to",
            ],
            ("Transfers", "mixed"),
        ),
        (["venmo", "cash app", "cashapp"], ("P2P", "mixed")),
        (["atm withdrawal"], ("Cash", "mixed")),
        (["walmart com"], ("Retail", "discretionary")),
        (
            ["walmart", "wal mart", "wal-mart", "wm supercenter", "target", "costco", "sam's club", "sams club"],
            ("Household", "mixed"),
        ),
        (["publix", "whole foods", "wholefds", "food patch", "aldi", "kroger", "trader joe"], ("Groceries", "essential")),
        (
            [
                "dukeenergy",
                "duke energy",
                "utilities",
                "mortgage",
                "comcast",
                "xfinity",
                "att",
                "a t t",
                "verizon",
                "tmobile",
                "t mobile",
                "spectrum",
                "frontier",
                "waste pro",
            ],
            ("Bills", "essential"),
        ),
        (["geico", "statefarm", "state farm", "progressive", "allstate", "insurance", "ins prem"], ("Insurance", "essential")),
        (
            [
                "cvs",
                "walgreens",
                "urgent care",
                "pharmacy",
                "medical",
                "healthcare",
                "doctor",
                "dental",
                "ortho",
                "labcorp",
                "dermatology",
                "womencare",
                "family care",
            ],
            ("Healthcare", "essential"),
        ),
        (
            ["shell", "speedway", "gas", "chevron", "exxon", "texaco", "marathon", "wawa", "circle k", "7-eleven", "7 eleven", "buc-ee", "buc ee"],
            ("Gas", "essential"),
        ),
        (
            ["uber", "lyft", "parking", "toll", "sunpass", "jiffy lube", "valvoline", "midas", "firestone", "pep boys"],
            ("Transportation", "essential"),
        ),
        (["lowes", "lowe s", "home depot", "menards", "ace hardware"], ("Home", "discretionary")),
        (["planet fitness", "gym", "ymca", "fitness", "largo rec", "rec center"], ("Fitness", "discretionary")),
        (
            [
                "spotify",
                "cloudflare",
                "prime",
                "netflix",
                "hulu",
                "disney",
                "hbo",
                "apple music",
                "youtube",
                "openai",
                "chatgpt",
                "claude",
                "anthropic",
                "google one",
                "sunbiz",
                "chamber",
            ],
            ("Subscriptions", "discretionary"),
        ),
        (
            [
                "target",
                "tjmaxx",
                "tj maxx",
                "t j maxx",
                "american eagle",
                "sephora",
                "amazon",
                "dillard",
                "aerie",
                "poshmark",
                "alo-yoga",
                "alo yoga",
                "marshalls",
                "michaels",
                "adidas",
                "edikted",
            ],
            ("Retail", "discretionary"),
        ),
        (
            [
                "carnival",
                "hotel",
                "suites",
                "airbnb",
                "marriott",
                "hilton",
                "delta",
                "united",
                "southwest",
                "international tampa",
                "tampa intl",
                "airport",
            ],
            ("Travel", "discretionary"),
        ),
        (
            [
                "chipotle",
                "bonefish",
                "cantina",
                "mcdonald",
                "starbucks",
                "dunkin",
                "chick fil",
                "wendy",
                "taco bell",
                "subway",
                "pizza",
                "grubhub",
                "doordash",
                "ubereats",
                "thai",
                "sushi",
                "cinco soles",
                "auntie anne",
            ],
            ("Dining", "discretionary"),
        ),
    ]
    for keywords, classification in rules:
        if any(keyword in normalized for keyword in keywords):
            return classification

    if amount is not None:
        if MIN_SUBSCRIPTION_AMOUNT <= amount <= MAX_SUBSCRIPTION_AMOUNT:
            return ("Subscriptions", "discretionary")
        if amount >= BILLS_AMOUNT_THRESHOLD:
            return ("Bills", "essential")

    return ("Household", "mixed")


def _classification_for_flow(
    *,
    raw_merchant: str,
    description: str,
    amount: float | None,
    flow_type: str,
) -> tuple[str, str]:
    if flow_type == "income":
        return ("Income", "essential")
    if flow_type == "refund":
        return _classify_merchant(
            raw_merchant=raw_merchant,
            description=description,
            amount=amount,
        )
    if flow_type in {"payment", "transfer_in", "transfer_out", "investment"}:
        return ("Transfers", "mixed")
    return _classify_merchant(
        raw_merchant=raw_merchant,
        description=description,
        amount=amount,
    )


def _looks_like_mixed_big_box_merchant(*, raw_merchant: str, description: str) -> bool:
    normalized = _merchant_root(f"{raw_merchant} {description}")
    return any(
        keyword in normalized
        for keyword in (
            "walmart",
            "wal mart",
            "wal mart",
            "wm supercenter",
            "target",
            "costco",
            "sam s club",
            "sams club",
        )
    )


def _is_refund_like_text(*, raw_merchant: str, description: str) -> bool:
    normalized = _merchant_root(f"{raw_merchant} {description}")
    return "refund" in normalized or "return" in normalized


def _effective_transaction_flow(
    *,
    flow_type: str | None,
    raw_merchant: str,
    description: str,
    source_type: str | None = None,
) -> str:
    normalized = (flow_type or "").strip().lower()
    if _is_refund_like_text(raw_merchant=raw_merchant, description=description):
        return "refund"
    if normalized:
        return normalized
    if (source_type or "").strip().lower() == "credit_card":
        return _classify_statement_flow(description)
    return "expense"


def _effective_transaction_classification(
    *,
    flow_type: str,
    raw_merchant: str,
    description: str,
    amount: float | None,
    stored_category: str | None,
    stored_essentiality: str | None,
    merchant_metadata: dict[str, Any] | None,
) -> tuple[str, str]:
    if isinstance(merchant_metadata, dict) and isinstance(merchant_metadata.get("manual_rule"), dict):
        return (
            (stored_category or "Uncategorized").strip() or "Uncategorized",
            (stored_essentiality or "mixed").strip() or "mixed",
        )

    resolved_category, resolved_essentiality = _classification_for_flow(
        raw_merchant=raw_merchant,
        description=description,
        amount=amount,
        flow_type=flow_type,
    )
    stored_category_text = (stored_category or "").strip()
    stored_essentiality_text = (stored_essentiality or "").strip()
    if (
        resolved_category == "Household"
        and stored_category_text
        and stored_category_text not in {"Household", "Uncategorized"}
        and not _looks_like_mixed_big_box_merchant(
            raw_merchant=raw_merchant,
            description=description,
        )
    ):
        return (
            stored_category_text,
            stored_essentiality_text or resolved_essentiality,
        )
    return resolved_category, resolved_essentiality

"""Merchant normalization and household transaction classification helpers."""

from __future__ import annotations

import re
from typing import Any

from app.services._household_report_builder import _merchant_root
from app.services._household_spend_filters import looks_like_investment_activity

MIN_SUBSCRIPTION_AMOUNT = 5.0
MAX_SUBSCRIPTION_AMOUNT = 25.0
BILLS_AMOUNT_THRESHOLD = 800.0

_PLAID_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "BANK_FEES": ("Bills", "essential"),
    "ENTERTAINMENT_MUSIC_AND_AUDIO": ("Subscriptions", "discretionary"),
    "ENTERTAINMENT_OTHER_ENTERTAINMENT": ("Entertainment", "discretionary"),
    "ENTERTAINMENT_SPORTING_EVENTS_AMUSEMENT_PARKS_AND_MUSEUMS": (
        "Entertainment",
        "discretionary",
    ),
    "ENTERTAINMENT_TV_AND_MOVIES": ("Subscriptions", "discretionary"),
    "FOOD_AND_DRINK_FAST_FOOD": ("Dining", "discretionary"),
    "FOOD_AND_DRINK_GROCERIES": ("Groceries", "essential"),
    "FOOD_AND_DRINK_OTHER_FOOD_AND_DRINK": ("Dining", "discretionary"),
    "FOOD_AND_DRINK_RESTAURANT": ("Dining", "discretionary"),
    "GENERAL_MERCHANDISE_CLOTHING_AND_ACCESSORIES": (
        "Retail",
        "discretionary",
    ),
    "GENERAL_MERCHANDISE_CONVENIENCE_STORES": ("Retail", "discretionary"),
    "GENERAL_MERCHANDISE_DEPARTMENT_STORES": ("Retail", "discretionary"),
    "GENERAL_MERCHANDISE_DISCOUNT_STORES": ("Household", "mixed"),
    "GENERAL_MERCHANDISE_ONLINE_MARKETPLACES": ("Retail", "discretionary"),
    "GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE": (
        "Retail",
        "discretionary",
    ),
    "GENERAL_MERCHANDISE_PET_SUPPLIES": ("Household", "mixed"),
    "GENERAL_MERCHANDISE_SPORTING_GOODS": ("Retail", "discretionary"),
    "GENERAL_MERCHANDISE_SUPERSTORES": ("Household", "mixed"),
    "GENERAL_SERVICES_AUTOMOTIVE": ("Transportation", "essential"),
    "GENERAL_SERVICES_EDUCATION": ("Education", "essential"),
    "GENERAL_SERVICES_OTHER_GENERAL_SERVICES": ("Subscriptions", "discretionary"),
    "GOVERNMENT_AND_NON_PROFIT_DONATIONS": ("Donations", "discretionary"),
    "GOVERNMENT_AND_NON_PROFIT_GOVERNMENT_DEPARTMENTS_AND_AGENCIES": (
        "Bills",
        "essential",
    ),
    "GOVERNMENT_AND_NON_PROFIT_OTHER_GOVERNMENT_AND_NON_PROFIT": (
        "Donations",
        "discretionary",
    ),
    "HOME_IMPROVEMENT_FURNITURE": ("Home", "discretionary"),
    "HOME_IMPROVEMENT_HARDWARE": ("Home", "discretionary"),
    "LOAN_PAYMENTS": ("Debt Payments", "mixed"),
    "MEDICAL": ("Healthcare", "essential"),
    "MEDICAL_DENTAL_CARE": ("Healthcare", "essential"),
    "MEDICAL_OTHER_MEDICAL": ("Healthcare", "essential"),
    "MEDICAL_PHARMACIES_AND_SUPPLEMENTS": ("Healthcare", "essential"),
    "MEDICAL_PRIMARY_CARE": ("Healthcare", "essential"),
    "OTHER_OTHER": ("Household", "mixed"),
    "PERSONAL_CARE_GYMS_AND_FITNESS_CENTERS": ("Fitness", "discretionary"),
    "PERSONAL_CARE_HAIR_AND_BEAUTY": ("Personal Care", "discretionary"),
    "RENT_AND_UTILITIES_OTHER_UTILITIES": ("Bills", "essential"),
    "TRANSFER_OUT_INVESTMENT_AND_RETIREMENT_FUNDS": ("Transfers", "mixed"),
    "TRANSPORTATION": ("Transportation", "essential"),
    "TRANSPORTATION_GAS": ("Gas", "essential"),
    "TRANSPORTATION_PARKING": ("Transportation", "essential"),
    "TRANSPORTATION_TOLLS": ("Transportation", "essential"),
    "TRAVEL_FLIGHTS": ("Travel", "discretionary"),
    "TRAVEL_LODGING": ("Travel", "discretionary"),
    "TRAVEL_OTHER_TRAVEL": ("Travel", "discretionary"),
}


def _canonical_merchant_name(raw_merchant: str) -> str:
    root = _merchant_root(raw_merchant)
    if not root:
        return raw_merchant.strip() or "Unknown merchant"
    collapsed = root.replace(" ", "")
    if "walmart" in collapsed or "wmsupercenter" in collapsed:
        store_match = re.search(r"#\s?(\d{4})", raw_merchant)
        location_match = re.search(
            r"(ANYTOWN|SPRINGFIELD|RIVERTON|RIVERTON)\s+FL",
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


def _category_key(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", (value or "").strip().upper()).strip("_")


def _looks_like_raw_taxonomy_enum(value: str | None) -> bool:
    """Return True for upstream SCREAMING_SNAKE enums (e.g. LOAN_PAYMENTS_OTHER_PAYMENT).

    These must never reach a user-facing surface; when one is unmapped we drop back
    to merchant-based classification rather than echoing the raw enum as a category.
    """
    text = (value or "").strip()
    if "_" not in text:
        return False
    return text == text.upper() and re.fullmatch(r"[A-Z0-9_]+", text) is not None


def _canonical_category_from_taxonomy(
    *,
    category: str | None,
    essentiality: str | None = None,
) -> tuple[str, str] | None:
    """Map upstream taxonomy labels into Portfolio AI's compact spend taxonomy."""
    key = _category_key(category)
    if not key:
        return None
    mapped = _PLAID_CATEGORY_MAP.get(key)
    prefix_map = (
        ("MEDICAL_", ("Healthcare", "essential")),
        ("FOOD_AND_DRINK_", ("Dining", "discretionary")),
        ("GENERAL_MERCHANDISE_", ("Retail", "discretionary")),
        ("HOME_IMPROVEMENT_", ("Home", "discretionary")),
        ("LOAN_PAYMENTS_", ("Debt Payments", "mixed")),
        ("RENT_AND_UTILITIES_", ("Bills", "essential")),
        ("TRANSPORTATION_", ("Transportation", "essential")),
        ("TRAVEL_", ("Travel", "discretionary")),
    )
    if mapped is None:
        mapped = next(
            (classification for prefix, classification in prefix_map if key.startswith(prefix)),
            None,
        )
    if mapped is None and category and not _looks_like_raw_taxonomy_enum(category):
        normalized_category = re.sub(r"\s+", " ", category).strip()
        normalized_essentiality = (essentiality or "mixed").strip() or "mixed"
        mapped = (normalized_category, normalized_essentiality)
    return mapped


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
        (["venmo", "cash app", "cashapp"], ("Peer Payments", "mixed")),
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
        (
            [
                "lowes",
                "lowe s",
                "home depot",
                "menards",
                "ace hardware",
                "furniture",
                "wayfair",
            ],
            ("Home", "discretionary"),
        ),
        (["planet fitness", "gym", "ymca", "fitness", "anytown rec", "rec center"], ("Fitness", "discretionary")),
        (
            [
                "audible",
                "spotify",
                "cloudflare",
                "pandora",
                "prime",
                "netflix",
                "hulu",
                "disney",
                "hbo",
                "apple music",
                "youtube",
                "youtube premium",
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
                "restaurant",
                "breakfast",
                "cafe",
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
    if looks_like_investment_activity(description=description, merchant=raw_merchant):
        return "investment"
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
    canonical_stored = _canonical_category_from_taxonomy(
        category=stored_category_text,
        essentiality=stored_essentiality_text,
    )
    if (
        canonical_stored is not None
        and canonical_stored[0] != stored_category_text
        and canonical_stored[0] not in {"Uncategorized", ""}
        and not _looks_like_mixed_big_box_merchant(
            raw_merchant=raw_merchant,
            description=description,
        )
    ):
        return canonical_stored
    if (
        resolved_category == "Household"
        and stored_category_text
        and stored_category_text not in {"Household", "Uncategorized"}
        and not _looks_like_raw_taxonomy_enum(stored_category_text)
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

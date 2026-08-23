"""The one place that decides what a category is and whether it is a need.

Categories were keyed as ``category + essentiality`` everywhere they were
counted, and nothing guaranteed a category kept the same essentiality from one
row to the next. So the Budget legend showed "Transportation" twice and
"Household" twice, needs-versus-wants moved without anyone touching anything,
and Plaid's raw taxonomy ("General Services Storage") sat in the legend beside
the curated names.

Essentiality is now a function of the category, not a second field that travels
alongside it and can disagree.
"""

from __future__ import annotations

ESSENTIAL = "essential"
DISCRETIONARY = "discretionary"
MIXED = "mixed"

# The curated taxonomy, and the single essentiality each category carries.
#
# `Household` is genuinely mixed rather than unclassified: a Costco run holds
# groceries and a television. `Cash`, `Peer Payments` and `Transfers` are mixed
# because the money left without saying what it bought.
CATEGORY_ESSENTIALITY: dict[str, str] = {
    "Bills": ESSENTIAL,
    "Insurance": ESSENTIAL,
    "Groceries": ESSENTIAL,
    "Gas": ESSENTIAL,
    "Healthcare": ESSENTIAL,
    "Transportation": ESSENTIAL,
    "Education": ESSENTIAL,
    "Income": ESSENTIAL,
    "Household": MIXED,
    "Cash": MIXED,
    "Peer Payments": MIXED,
    "Transfers": MIXED,
    "Debt Payments": MIXED,
    # Home is the furniture, the hardware store and the garden nursery. The
    # property tax and the HOA that used to sit here as the category's only
    # "essential" rows are bills, and BILL_CONCEPTS moves them there, which is
    # what lets this one stay honestly discretionary.
    "Home": DISCRETIONARY,
    "Retail": DISCRETIONARY,
    "Dining": DISCRETIONARY,
    "Subscriptions": DISCRETIONARY,
    "Travel": DISCRETIONARY,
    "Entertainment": DISCRETIONARY,
    "Fitness": DISCRETIONARY,
    "Personal Care": DISCRETIONARY,
    "Girls": DISCRETIONARY,
    "Donations": DISCRETIONARY,
}

FALLBACK_CATEGORY = "Household"

# Upstream labels that leaked into the legend, mapped to what they actually are.
CATEGORY_ALIASES: dict[str, str] = {
    "general services insurance": "Insurance",
    "general services storage": "Household",
    "general services automotive": "Transportation",
    "general services education": "Education",
    "bank fees other bank fees": "Bills",
    "uncategorized": "Household",
    "other": "Household",
    "shopping": "Retail",
    "utilities": "Bills",
    "rent": "Bills",
    "mortgage": "Bills",
    "auto": "Transportation",
    "gas & fuel": "Gas",
    "restaurants": "Dining",
    "food & dining": "Dining",
    "health": "Healthcare",
    "medical": "Healthcare",
    "loan payments": "Debt Payments",
}

# Whole families rather than single labels. Checked after the explicit aliases,
# so "General Services Insurance" still lands on Insurance rather than here.
CATEGORY_ALIAS_PREFIXES: tuple[tuple[str, str], ...] = (
    ("general services", "Household"),
    ("general merchandise", "Retail"),
    ("bank fees", "Bills"),
    ("rent and utilities", "Bills"),
    ("food and drink", "Dining"),
    ("home improvement", "Home"),
    ("loan payments", "Debt Payments"),
    ("government and non profit", "Donations"),
    ("personal care", "Personal Care"),
    ("medical", "Healthcare"),
    ("transportation", "Transportation"),
    ("entertainment", "Entertainment"),
    ("travel", "Travel"),
    ("income", "Income"),
    ("transfer", "Transfers"),
)

# Phrases that make a charge a housing bill whatever category it landed in. The
# reference cases are the $2,144.48 Pinellas County property tax and the Harbor
# Hills HOA, which sat in Home as its only essential rows and dragged the whole
# category between needs and wants depending on which row was being read.
BILL_CONCEPTS: tuple[str, ...] = (
    "property tax",
    "tax collector",
    "homeowners association",
    "home owners association",
    "association dues",
    "hoa dues",
    "hoa payment",
)


def _looks_like_raw_enum(text: str) -> bool:
    """True for upstream SCREAMING_SNAKE labels that must never reach a legend."""
    return "_" in text and text == text.upper()


def normalize_category(category: str | None) -> str:
    """Return the curated category for any label the pipeline produces.

    A label that is none of the curated names and none of the known upstream
    families is kept as written. The household names its own categories -- one of
    them is literally "Girls" -- and flattening those into the fallback would be
    a worse lie than the one this function exists to fix.
    """
    raw = str(category or "").strip()
    text = " ".join(raw.replace("_", " ").split())
    if not text:
        return FALLBACK_CATEGORY
    key = text.lower()
    known = (
        text
        if text in CATEGORY_ESSENTIALITY
        else CATEGORY_ALIASES.get(key)
        or (text.title() if text.title() in CATEGORY_ESSENTIALITY else None)
        or next(
            (curated for prefix, curated in CATEGORY_ALIAS_PREFIXES if key.startswith(prefix)),
            None,
        )
    )
    if known is not None:
        return known
    return FALLBACK_CATEGORY if _looks_like_raw_enum(raw) else text


def essentiality_for(category: str | None) -> str:
    """The one essentiality this category carries, everywhere it is counted.

    A category nobody has classified is `mixed` rather than a guess, and it is
    the same `mixed` every time it is read -- which is the whole point.
    """
    return CATEGORY_ESSENTIALITY.get(normalize_category(category), MIXED)


def looks_like_housing_bill(*text_parts: str | None) -> bool:
    """True for a charge that is a housing bill regardless of where it landed."""
    haystack = " ".join(part for part in text_parts if part).lower()
    return any(concept in haystack for concept in BILL_CONCEPTS)


def canonical_classification(
    category: str | None,
    *,
    merchant: str | None = None,
    description: str | None = None,
) -> tuple[str, str]:
    """Return the (category, essentiality) pair every surface should agree on."""
    if looks_like_housing_bill(category, merchant, description):
        return ("Bills", CATEGORY_ESSENTIALITY["Bills"])
    resolved = normalize_category(category)
    return (resolved, essentiality_for(resolved))


__all__ = [
    "BILL_CONCEPTS",
    "CATEGORY_ALIASES",
    "CATEGORY_ALIAS_PREFIXES",
    "CATEGORY_ESSENTIALITY",
    "DISCRETIONARY",
    "ESSENTIAL",
    "FALLBACK_CATEGORY",
    "MIXED",
    "canonical_classification",
    "essentiality_for",
    "looks_like_housing_bill",
    "normalize_category",
]

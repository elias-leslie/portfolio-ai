"""Issuer application-rule predicates for the rotation engine.

Pure, date-fixture-unit-testable. These encode *general public rules* — heuristics
that drive sequencing and surface warnings; they are NOT guaranteed approval and
NOT hard blocks. The rotation engine threads a running IssuerRuleState across
quarters and asks these predicates whether opening a product this quarter trips a
rule (returns warning strings) and whether its welcome bonus is still earnable.

Quarter math: 1 quarter = 3 months, so 24 months = 8 quarters, 48 months = 16.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.credit_cards import CreditCardProduct

QUARTERS_PER_24_MONTHS = 8
QUARTERS_PER_48_MONTHS = 16
QUARTERS_PER_6_MONTHS = 2
CHASE_5_24_THRESHOLD = 5

_SAPPHIRE_SLUGS = frozenset({"chase-sapphire-preferred", "chase-sapphire-reserve"})


@dataclass
class IssuerRuleState:
    """Running history threaded through the rotation horizon.

    ``opens`` records every card opening as (quarter_index, product). Pre-existing
    owned cards may be seeded with negative quarter indices to represent opens
    before the horizon start. ``amex_products_opened`` is the lifetime set of Amex
    product slugs ever opened (welcome bonus is once per lifetime per product).
    """

    opens: list[tuple[int, CreditCardProduct]] = field(default_factory=list)
    amex_products_opened: set[str] = field(default_factory=set)

    def record_open(self, quarter_index: int, product: CreditCardProduct) -> None:
        self.opens.append((quarter_index, product))
        if (product.issuer_rules or {}).get("amex_once_per_lifetime"):
            self.amex_products_opened.add(product.slug)


def _opens_in_window(state: IssuerRuleState, *, quarter_index: int, lookback_quarters: int) -> int:
    """Count card opens in (quarter_index - lookback, quarter_index)."""
    start = quarter_index - lookback_quarters
    return sum(1 for (q, _) in state.opens if start <= q < quarter_index)


def welcome_eligible(product: CreditCardProduct, state: IssuerRuleState) -> bool:
    """Whether the welcome bonus is still earnable (lifetime rules only)."""
    rules = product.issuer_rules or {}
    return not (rules.get("amex_once_per_lifetime") and product.slug in state.amex_products_opened)


def evaluate_open(
    product: CreditCardProduct, *, quarter_index: int, state: IssuerRuleState
) -> list[str]:
    """Warnings (not blocks) for opening ``product`` at ``quarter_index``."""
    warnings: list[str] = []
    rules = product.issuer_rules or {}

    if rules.get("chase_5_24"):
        recent = _opens_in_window(
            state, quarter_index=quarter_index, lookback_quarters=QUARTERS_PER_24_MONTHS
        )
        if recent >= CHASE_5_24_THRESHOLD:
            warnings.append(
                f"Likely blocked by Chase 5/24: {recent} new cards opened in the "
                "trailing 24 months (general public rule, not guaranteed)."
            )

    if rules.get("family") == "sapphire":
        for q, opened in state.opens:
            if (
                opened.slug in _SAPPHIRE_SLUGS
                and quarter_index - q < QUARTERS_PER_48_MONTHS
            ):
                warnings.append(
                    "Sapphire welcome bonus is once per 48 months across the family, "
                    "and Preferred + Reserve cannot be held at the same time."
                )
                break

    if rules.get("amex_once_per_lifetime") and product.slug in state.amex_products_opened:
        warnings.append(
            "Amex welcome bonus is once per lifetime per product — already opened, "
            "so no bonus will be earned again."
        )

    if rules.get("capital_one_1_per_6mo"):
        for q, opened in state.opens:
            if (opened.issuer == product.issuer) and (
                quarter_index - q < QUARTERS_PER_6_MONTHS
            ):
                warnings.append(
                    "Capital One generally approves about one personal card per 6 months."
                )
                break

    return warnings

"""Deterministic credit-card rewards valuation + ranking.

Pure, no-LLM, unit-testable. The CardManagementService facade loads products and
the spend profile from the DB and hands them here. Every output states its
assumptions (cents-per-point, amortization window, category mapping) and carries
the standing disclaimer — this is modeling of public reward structures, not
personalized financial advice.
"""

from __future__ import annotations

from app.models.credit_cards import (
    CardRanking,
    CardRewardEstimate,
    CategoryContribution,
    CreditCardProduct,
    SpendProfile,
)
from app.models.household_finance_types import HouseholdSpendingView

# Canonical reward buckets used by both the catalog multipliers and the profile.
REWARD_BUCKETS: tuple[str, ...] = ("dining", "travel", "flights", "groceries", "gas", "other")

# Map canonical household transaction categories onto reward buckets. Anything not
# listed and not excluded falls through to "other" (base earn).
CATEGORY_TO_REWARD_BUCKET: dict[str, str] = {
    "Dining": "dining",
    "Groceries": "groceries",
    "Gas": "gas",
    "Travel": "travel",
    # Premium travel cards generally count transit/rideshare as travel; surfaced
    # as an assumption so the user can override the mix.
    "Transportation": "travel",
}

# Categories that are not card purchases (cash movement, debt, income, brokerage)
# and so never earn rewards — dropped from the spend profile.
EXCLUDED_CATEGORIES: frozenset[str] = frozenset(
    {"Cash", "Debt Payments", "Income", "Transfers", "Peer Payments", "Investments"}
)

# How much of a stated statement credit a typical user actually realizes.
CREDIT_REALIZATION: dict[str, float] = {"easy": 1.0, "moderate": 0.6, "hard": 0.25}

# Valuation stance scales the balanced/TPG-style floor. Cash-like programs
# (<=1.0c) are never scaled — a cent is a cent.
STANCE_FACTOR: dict[str, float] = {"conservative": 0.8, "balanced": 1.0, "optimistic": 1.25}

DEFAULT_MONTHLY_TOTAL: float = 6500.0
DEFAULT_BUCKET_MIX: dict[str, float] = {
    "dining": 1200.0,
    "groceries": 900.0,
    "gas": 300.0,
    "travel": 600.0,
    "flights": 0.0,
    "other": 3500.0,
}


class CardRewardsService:
    """Stateless valuation engine. Construct once and reuse."""

    def build_spend_profile(self, view: HouseholdSpendingView) -> SpendProfile:
        """Derive a reward-bucket spend profile from real transactions (3-month
        window recommended). Falls back to a representative default when there is
        no data."""
        by_bucket: dict[str, float] = dict.fromkeys(REWARD_BUCKETS, 0.0)
        for category in view.categories:
            if category.category in EXCLUDED_CATEGORIES:
                continue
            bucket = CATEGORY_TO_REWARD_BUCKET.get(category.category, "other")
            by_bucket[bucket] += max(category.gross_monthly_spend, 0.0)

        total = round(sum(by_bucket.values()), 2)
        if total <= 0:
            return SpendProfile(
                monthly_total=DEFAULT_MONTHLY_TOTAL,
                by_bucket=dict(DEFAULT_BUCKET_MIX),
                source="default",
            )
        return SpendProfile(
            monthly_total=total,
            by_bucket={bucket: round(value, 2) for bucket, value in by_bucket.items() if value > 0},
            source="transactions_3m",
        )

    def apply_overrides(
        self,
        profile: SpendProfile,
        *,
        monthly_total: float | None = None,
        by_bucket: dict[str, float] | None = None,
    ) -> SpendProfile:
        """Layer user overrides onto a derived profile."""
        if by_bucket:
            cleaned = {k: round(float(v), 2) for k, v in by_bucket.items() if float(v) > 0}
            total = round(monthly_total if monthly_total is not None else sum(cleaned.values()), 2)
            return SpendProfile(monthly_total=total, by_bucket=cleaned, source="user_override")
        if monthly_total is not None and monthly_total > 0:
            current = profile.monthly_total or sum(DEFAULT_BUCKET_MIX.values())
            base = profile.by_bucket or DEFAULT_BUCKET_MIX
            scale = monthly_total / current if current > 0 else 0.0
            scaled = {k: round(v * scale, 2) for k, v in base.items() if v * scale > 0}
            return SpendProfile(monthly_total=round(monthly_total, 2), by_bucket=scaled, source="user_override")
        return profile

    def point_value_cents(
        self,
        product: CreditCardProduct,
        *,
        stance: str = "balanced",
        overrides: dict[str, float] | None = None,
    ) -> float:
        """Resolve the cents-per-point used for this product's program."""
        base = product.est_point_value_cents if product.est_point_value_cents is not None else 1.0
        program = product.point_program or "cash"
        if overrides and program in overrides:
            return round(float(overrides[program]), 4)
        if base <= 1.0:  # cash-like — fixed value, not scaled by stance
            return round(base, 4)
        return round(base * STANCE_FACTOR.get(stance, 1.0), 4)

    def evaluate_card(
        self,
        product: CreditCardProduct,
        profile: SpendProfile,
        *,
        point_value_cents: float,
        amortization_years: int = 3,
    ) -> CardRewardEstimate:
        """Value a single card for a spend profile.

        earn = Σ_bucket monthly_spend·12·multiplier·cpp/100
        welcome counts only if the min-spend is reachable at the assumed rate.
        """
        contributions: list[CategoryContribution] = []
        earn_value = 0.0
        for bucket, monthly_spend in profile.by_bucket.items():
            if monthly_spend <= 0:
                continue
            multiplier = product.reward_multipliers.get(bucket)
            if multiplier is None:
                multiplier = product.reward_multipliers.get("other", 1.0)
            annual = monthly_spend * 12 * float(multiplier) * (point_value_cents / 100.0)
            earn_value += annual
            contributions.append(
                CategoryContribution(
                    bucket=bucket,
                    monthly_spend=round(monthly_spend, 2),
                    multiplier=float(multiplier),
                    point_value_cents=point_value_cents,
                    annual_value=round(annual, 2),
                )
            )

        credits_value = sum(
            credit.annual_value * CREDIT_REALIZATION.get(credit.type, 0.6) for credit in product.credits
        )
        annual_value = earn_value + credits_value - product.annual_fee

        window_months = (product.welcome_window_days or 90) / 30.0
        reachable_spend = profile.monthly_total * window_months
        min_spend = product.welcome_min_spend or 0.0
        has_welcome = bool(product.welcome_bonus_points or product.welcome_bonus_cash)
        welcome_reachable = (min_spend <= 0) or (reachable_spend >= min_spend)
        welcome_value = 0.0
        if welcome_reachable:
            welcome_value = (product.welcome_bonus_points or 0) * (point_value_cents / 100.0) + (
                product.welcome_bonus_cash or 0.0
            )

        warnings: list[str] = []
        if has_welcome and not welcome_reachable:
            warnings.append(
                f"Welcome bonus excluded: ${min_spend:,.0f} minimum spend over "
                f"{product.welcome_window_days}d is not reachable at "
                f"${profile.monthly_total:,.0f}/mo."
            )
        if any(credit.type == "hard" for credit in product.credits):
            warnings.append("Some statement credits are hard to fully use; valued at a fraction.")

        first_year_value = annual_value + welcome_value
        steady_state_value = annual_value + (
            welcome_value / amortization_years if amortization_years > 0 else 0.0
        )

        return CardRewardEstimate(
            product_id=product.id,
            slug=product.slug,
            issuer=product.issuer,
            product_name=product.product_name,
            card_kind=product.card_kind,
            annual_fee=round(product.annual_fee, 2),
            assumed_point_value_cents=point_value_cents,
            earn_value=round(earn_value, 2),
            credits_value=round(credits_value, 2),
            annual_value=round(annual_value, 2),
            welcome_value=round(welcome_value, 2),
            welcome_reachable=welcome_reachable,
            first_year_value=round(first_year_value, 2),
            amortization_years=amortization_years,
            steady_state_value=round(steady_state_value, 2),
            category_contributions=contributions,
            warnings=warnings,
        )

    def rank(
        self,
        products: list[CreditCardProduct],
        profile: SpendProfile,
        *,
        stance: str = "balanced",
        overrides: dict[str, float] | None = None,
        amortization_years: int = 3,
    ) -> CardRanking:
        """Rank products by first-year and steady-state value for the profile."""
        estimates = [
            self.evaluate_card(
                product,
                profile,
                point_value_cents=self.point_value_cents(product, stance=stance, overrides=overrides),
                amortization_years=amortization_years,
            )
            for product in products
        ]
        by_first_year = sorted(estimates, key=lambda e: e.first_year_value, reverse=True)
        by_steady_state = sorted(estimates, key=lambda e: e.steady_state_value, reverse=True)

        programs_used = sorted({p.point_program or "cash" for p in products})
        cpp_lines = [
            f"{est.slug}: {est.assumed_point_value_cents:.2f}¢/pt"
            for est in sorted(estimates, key=lambda e: e.slug)
        ]
        assumptions = [
            f"Valuation stance: {stance} (point values scaled from the balanced/TPG-style floor).",
            f"Welcome bonuses amortized over {amortization_years} years for steady-state ranking.",
            "Transit/rideshare spend is treated as travel; transfer-partner upside is excluded.",
            "Welcome bonus counted only when the minimum spend is reachable at the assumed rate.",
            "Statement credits valued by realization difficulty (easy 100% / moderate 60% / hard 25%).",
            f"Programs valued: {', '.join(programs_used)}.",
            "Per-card cents-per-point — " + "; ".join(cpp_lines) + ".",
        ]

        return CardRanking(
            spend_profile=profile,
            valuation_stance=stance,
            amortization_years=amortization_years,
            by_first_year=by_first_year,
            by_steady_state=by_steady_state,
            assumptions=assumptions,
        )

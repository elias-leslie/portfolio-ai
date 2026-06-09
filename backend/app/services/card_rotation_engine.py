"""Deterministic 90-day card rotation engine.

Pure and unit-testable. Greedy per-quarter selection over the horizon: each
quarter picks the single active card maximizing marginal value = welcome (if a
new open with the bonus reachable & eligible) + quarterly earn - prorated annual
fee, honoring issuer rules via a running IssuerRuleState (5/24, Sapphire 48-mo,
Amex lifetime, Cap One 1/6) and a Chase-first weight so Chase cards are sequenced
before 5/24 accumulates.

Output projects cumulative value per quarter vs a best keep-forever single-card
baseline. Issuer rules surface as warnings, never hard blocks (plan section 6/11).
"""

from __future__ import annotations

from app.models.credit_cards import (
    CardRewardEstimate,
    CreditCardProduct,
    RotationCumulativePoint,
    RotationPlanView,
    RotationStepView,
    SpendProfile,
)
from app.services._card_issuer_rules import IssuerRuleState, evaluate_open, welcome_eligible
from app.services.card_rewards_service import CardRewardsService

# Modest nudge (dollars) so a Chase card is preferred among near-ties while 5/24
# headroom exists — captures Chase bonuses before other opens use up the slots.
CHASE_FIRST_WEIGHT = 75.0

_WELCOME_OBJECTIVES = frozenset({"rotate_90d", "maximize_welcome_bonuses"})


class CardRotationEngine:
    def __init__(self, rewards: CardRewardsService | None = None) -> None:
        self._rewards = rewards or CardRewardsService()

    def build_rotation_plan(
        self,
        products: list[CreditCardProduct],
        profile: SpendProfile,
        *,
        objective: str = "rotate_90d",
        horizon_quarters: int = 8,
        stance: str = "balanced",
        overrides: dict[str, float] | None = None,
        name: str | None = None,
    ) -> RotationPlanView:
        horizon_quarters = max(1, min(int(horizon_quarters), 40))
        horizon_years = horizon_quarters / 4.0
        # Personal cards only in v1.
        candidates = [p for p in products if p.card_kind == "personal"]

        # Pre-value every card once for this profile.
        estimates: dict[str, CardRewardEstimate] = {}
        product_by_slug: dict[str, CreditCardProduct] = {}
        for product in candidates:
            cpp = self._rewards.point_value_cents(product, stance=stance, overrides=overrides)
            estimates[product.slug] = self._rewards.evaluate_card(
                product, profile, point_value_cents=cpp, amortization_years=max(1, horizon_quarters // 4)
            )
            product_by_slug[product.slug] = product

        baseline_value, baseline_slug = self._best_baseline(estimates, horizon_years)

        welcome_factor = 1.0 if objective in _WELCOME_OBJECTIVES else 0.0
        state = IssuerRuleState()
        opened_slugs: set[str] = set()

        steps: list[RotationStepView] = []
        cumulative: list[RotationCumulativePoint] = []
        rotation_running = 0.0
        baseline_running = 0.0
        all_warnings: list[str] = []
        quarterly_spend = round(profile.monthly_total * 3, 2)

        for quarter_index in range(horizon_quarters):
            choice = self._pick_card(
                candidates,
                estimates,
                state=state,
                opened_slugs=opened_slugs,
                quarter_index=quarter_index,
                welcome_factor=welcome_factor,
            )
            if choice is None:
                break
            product = choice
            estimate = estimates[product.slug]
            is_new_open = product.slug not in opened_slugs
            eligible = welcome_eligible(product, state)
            welcome_captured = estimate.welcome_value if (is_new_open and eligible) else 0.0
            quarter_earn = round(estimate.earn_value / 4.0, 2)
            quarter_recurring = round(estimate.annual_value / 4.0, 2)  # earn + credits - fee, per quarter
            quarter_value = round(quarter_recurring + welcome_captured, 2)

            warnings = evaluate_open(product, quarter_index=quarter_index, state=state) if is_new_open else []
            if is_new_open and not eligible and (product.welcome_bonus_points or product.welcome_bonus_cash):
                warnings.append("Welcome bonus already earned on this product — opening adds earn only, no bonus.")
            for warning in warnings:
                if warning not in all_warnings:
                    all_warnings.append(warning)

            action = "open_and_spend" if is_new_open else (
                "hold" if (steps and steps[-1].product_slug == product.slug) else "switch_to"
            )

            steps.append(
                RotationStepView(
                    sequence_index=quarter_index,
                    quarter_label=f"Q{quarter_index + 1}",
                    product_id=product.id,
                    product_slug=product.slug,
                    product_name=product.product_name,
                    issuer=product.issuer,
                    action=action,
                    target_spend=quarterly_spend,
                    projected_welcome_value=round(welcome_captured, 2),
                    projected_earn_value=quarter_earn,
                    projected_value=quarter_value,
                    rule_warnings=warnings,
                )
            )

            if is_new_open:
                state.record_open(quarter_index, product)
                opened_slugs.add(product.slug)

            rotation_running = round(rotation_running + quarter_value, 2)
            baseline_quarter = self._baseline_quarter_value(estimates, baseline_slug, quarter_index)
            baseline_running = round(baseline_running + baseline_quarter, 2)
            cumulative.append(
                RotationCumulativePoint(
                    quarter_index=quarter_index + 1,
                    quarter_label=f"Q{quarter_index + 1}",
                    rotation_cumulative_value=rotation_running,
                    baseline_cumulative_value=baseline_running,
                )
            )

        projected_total = rotation_running
        assumptions = [
            f"Assumes ${profile.monthly_total:,.0f}/mo (${quarterly_spend:,.0f}/quarter), paid in full.",
            "One active card per quarter; welcome bonus captured only on a new open with the "
            "minimum spend reachable and the bonus still eligible.",
            "Annual fees and statement credits are prorated per quarter a card is held.",
            f"Baseline = best single keep-forever card ({baseline_slug or 'n/a'}) over the horizon.",
            "Issuer rules are general public heuristics surfaced as warnings — approval is never guaranteed.",
        ]

        return RotationPlanView(
            name=name or f"{objective} ({horizon_quarters}q)",
            objective=objective,
            horizon_quarters=horizon_quarters,
            spend_profile=profile,
            steps=steps,
            projected_total_value=projected_total,
            baseline_single_card_value=round(baseline_value, 2),
            baseline_product_slug=baseline_slug,
            uplift=round(projected_total - baseline_value, 2),
            cumulative_value=cumulative,
            warnings=all_warnings,
            assumptions=assumptions,
        )

    # -- internals --------------------------------------------------------

    def _pick_card(
        self,
        candidates: list[CreditCardProduct],
        estimates: dict[str, CardRewardEstimate],
        *,
        state: IssuerRuleState,
        opened_slugs: set[str],
        quarter_index: int,
        welcome_factor: float,
    ) -> CreditCardProduct | None:
        best: tuple[float, str] | None = None
        best_product: CreditCardProduct | None = None
        for product in candidates:
            estimate = estimates[product.slug]
            is_new_open = product.slug not in opened_slugs
            eligible = welcome_eligible(product, state)
            welcome = estimate.welcome_value if (is_new_open and eligible) else 0.0
            score = estimate.annual_value / 4.0 + welcome_factor * welcome
            if product.issuer == "Chase" and is_new_open:
                score += CHASE_FIRST_WEIGHT
            key = (round(score, 4), product.slug)
            if best is None or (key[0] > best[0]) or (key[0] == best[0] and key[1] < best[1]):
                best = key
                best_product = product
        return best_product

    def _best_baseline(
        self, estimates: dict[str, CardRewardEstimate], horizon_years: float
    ) -> tuple[float, str | None]:
        best_value = 0.0
        best_slug: str | None = None
        for slug, estimate in estimates.items():
            value = estimate.welcome_value + estimate.annual_value * horizon_years
            if best_slug is None or value > best_value:
                best_value = value
                best_slug = slug
        return best_value, best_slug

    def _baseline_quarter_value(
        self, estimates: dict[str, CardRewardEstimate], baseline_slug: str | None, quarter_index: int
    ) -> float:
        if baseline_slug is None:
            return 0.0
        estimate = estimates[baseline_slug]
        quarter_value = estimate.annual_value / 4.0
        if quarter_index == 0:
            quarter_value += estimate.welcome_value  # welcome earned once, in the first year
        return round(quarter_value, 2)

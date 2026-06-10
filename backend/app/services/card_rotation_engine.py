"""Deterministic two-player card rotation engine.

Pure and unit-testable. Greedy per-quarter selection over the horizon: each
quarter the household opens at most one new card — assigned to the player whose
issuer-rule state scores best — maximizing marginal value = welcome (if a new
open with the bonus reachable & eligible for that player) + quarterly earn -
prorated annual fee. Issuer rules run per player via one IssuerRuleState each
(5/24, Sapphire 48-mo, Amex lifetime, Cap One 1/6) with a Chase-first weight so
Chase cards are sequenced before 5/24 accumulates.

Why two players (plan §0a): a solo 90-day cadence opens 4 cards/year and crosses
Chase 5/24 within a year. Two players alternating (~2 opens/yr each) keep every
player under 5/24 indefinitely while the household still lands a bonus roughly
every quarter. Ties between equally scored players break toward the player with
fewer opens, so alternation emerges naturally.

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
from app.services.card_rewards_service import DEFAULT_CREDIT_STANCE, CardRewardsService

# Modest nudge (dollars) so a Chase card is preferred among near-ties while 5/24
# headroom exists — captures Chase bonuses before other opens use up the slots.
CHASE_FIRST_WEIGHT = 75.0

_WELCOME_OBJECTIVES = frozenset({"rotate_90d", "maximize_welcome_bonuses"})

DEFAULT_PLAYERS: tuple[str, ...] = ("p1", "p2")


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
        credit_stance: str = DEFAULT_CREDIT_STANCE,
        players: list[str] | None = None,
        name: str | None = None,
        extra_assumptions: list[str] | None = None,
    ) -> RotationPlanView:
        horizon_quarters = max(1, min(int(horizon_quarters), 40))
        horizon_years = horizon_quarters / 4.0
        players = [p for p in (players or list(DEFAULT_PLAYERS)) if p] or list(DEFAULT_PLAYERS)
        # Personal cards only in v1.
        candidates = [p for p in products if p.card_kind == "personal"]

        # Pre-value every card once for this profile.
        estimates: dict[str, CardRewardEstimate] = {}
        for product in candidates:
            cpp = self._rewards.point_value_cents(product, stance=stance, overrides=overrides)
            estimates[product.slug] = self._rewards.evaluate_card(
                product,
                profile,
                point_value_cents=cpp,
                amortization_years=max(1, horizon_quarters // 4),
                credit_stance=credit_stance,
            )

        baseline_value, baseline_slug = self._best_baseline(estimates, horizon_years)

        welcome_factor = 1.0 if objective in _WELCOME_OBJECTIVES else 0.0
        states: dict[str, IssuerRuleState] = {player: IssuerRuleState() for player in players}
        opened_by: dict[str, set[str]] = {player: set() for player in players}
        # First player to open a slug "owns" the physical card for hold steps.
        owner_of_slug: dict[str, str] = {}

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
                players=players,
                states=states,
                opened_by=opened_by,
                quarter_index=quarter_index,
                welcome_factor=welcome_factor,
            )
            if choice is None:
                break
            player, product = choice
            state = states[player]
            estimate = estimates[product.slug]
            is_new_open = product.slug not in opened_by[player]
            eligible = welcome_eligible(product, state)
            welcome_captured = estimate.welcome_value if (is_new_open and eligible) else 0.0
            quarter_earn = round(estimate.earn_value / 4.0, 2)
            quarter_recurring = round(estimate.annual_value / 4.0, 2)  # earn + credits - fee, per quarter
            quarter_value = round(quarter_recurring + welcome_captured, 2)

            warnings = (
                [f"{player}: {w}" for w in evaluate_open(product, quarter_index=quarter_index, state=state)]
                if is_new_open
                else []
            )
            if is_new_open and not eligible and (product.welcome_bonus_points or product.welcome_bonus_cash):
                warnings.append(
                    f"{player}: welcome bonus already earned on this product — opening adds earn only, no bonus."
                )
            for warning in warnings:
                if warning not in all_warnings:
                    all_warnings.append(warning)

            if is_new_open:
                action = "open_and_spend"
                step_player = player
            else:
                step_player = owner_of_slug.get(product.slug, player)
                action = "hold" if (steps and steps[-1].product_slug == product.slug) else "switch_to"

            steps.append(
                RotationStepView(
                    sequence_index=quarter_index,
                    quarter_label=f"Q{quarter_index + 1}",
                    product_id=product.id,
                    product_slug=product.slug,
                    product_name=product.product_name,
                    issuer=product.issuer,
                    player=step_player,
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
                opened_by[player].add(product.slug)
                owner_of_slug.setdefault(product.slug, player)

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
        opens_per_player = {player: len(slugs) for player, slugs in opened_by.items()}
        player_line = ", ".join(f"{player} opens {count}" for player, count in opens_per_player.items())
        assumptions = [
            f"Assumes ${profile.monthly_total:,.0f}/mo (${quarterly_spend:,.0f}/quarter), paid in full.",
            "One active rotating card per quarter; welcome bonus captured only on a new open "
            "with the minimum spend reachable and the bonus still eligible for that player.",
            f"Two-player household model ({len(players)} player(s): {player_line}) — issuer rules "
            "(5/24, Amex lifetime, Cap One 1/6, Sapphire 48-mo) tracked per player, so each "
            "player stays at ~2 opens/year while the household lands a bonus most quarters.",
            "Annual fees and statement credits are prorated per quarter a card is held.",
            f"Baseline = best single keep-forever card ({baseline_slug or 'n/a'}) over the horizon.",
            "Issuer rules are general public heuristics surfaced as warnings — approval is never guaranteed.",
        ]
        if extra_assumptions:
            assumptions.extend(extra_assumptions)

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
        players: list[str],
        states: dict[str, IssuerRuleState],
        opened_by: dict[str, set[str]],
        quarter_index: int,
        welcome_factor: float,
    ) -> tuple[str, CreditCardProduct] | None:
        """Best (player, product) this quarter.

        Rule warnings act as a soft penalty (a warned open scores below a clean
        one but is never excluded). Tie-breaks, in order: holding an
        already-open card beats a same-score duplicate open; then the player
        with fewer opens wins, so the two players alternate instead of one
        burning their 5/24; then first-seen (players/candidates list order)."""
        best_rank: tuple[float, int, int] | None = None
        best_choice: tuple[str, CreditCardProduct] | None = None
        for player in players:
            state = states[player]
            opens_so_far = len(opened_by[player])
            for product in candidates:
                estimate = estimates[product.slug]
                is_new_open = product.slug not in opened_by[player]
                eligible = welcome_eligible(product, state)
                welcome = estimate.welcome_value if (is_new_open and eligible) else 0.0
                score = estimate.annual_value / 4.0 + welcome_factor * welcome
                if product.issuer == "Chase" and is_new_open:
                    score += CHASE_FIRST_WEIGHT
                if is_new_open and evaluate_open(product, quarter_index=quarter_index, state=state):
                    score -= welcome_factor * welcome * 0.5 + CHASE_FIRST_WEIGHT
                rank = (round(score, 4), 0 if is_new_open else 1, -opens_so_far)
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_choice = (player, product)
        return best_choice

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

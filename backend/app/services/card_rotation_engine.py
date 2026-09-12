"""History-aware card rotation with dated full-fee cash flows."""

from __future__ import annotations

from datetime import date

from app.models.credit_cards import (
    CardRewardEstimate,
    CreditCardProduct,
    HouseholdCreditCard,
    RotationCumulativePoint,
    RotationPlanView,
    RotationStepView,
    SpendProfile,
)
from app.services._card_commitment_schedule import commitment_schedule
from app.services._card_issuer_rules import IssuerRuleState, evaluate_open, welcome_eligible
from app.services._card_rotation_cashflows import (
    HeldCard,
    add_months,
    anniversary_events,
    fee_events,
    owned_lifecycle,
    parse_day,
    total_fees,
)
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
        owned_cards: list[HouseholdCreditCard] | None = None,
        as_of: date | None = None,
        close_after_months: int | None = None,
    ) -> RotationPlanView:
        if close_after_months is not None and close_after_months < 13:
            raise ValueError("Model closures only after at least 13 months; first-year cancellations can forfeit rewards.")
        start = as_of or date.today()
        horizon_quarters = max(1, min(int(horizon_quarters), 40))
        players = list(dict.fromkeys(p for p in (players or list(DEFAULT_PLAYERS)) if p)) or list(DEFAULT_PLAYERS)
        candidates = [p for p in products if p.card_kind == "personal"]
        def estimate_profile(spend: SpendProfile) -> dict[str, CardRewardEstimate]:
            return {p.slug: self._rewards.evaluate_card(p, spend,
                    point_value_cents=self._rewards.point_value_cents(p, stance=stance, overrides=overrides),
                    amortization_years=max(1, horizon_quarters//4), credit_stance=credit_stance) for p in candidates}
        owned = owned_cards or []
        held, all_warnings = owned_lifecycle(owned, start)
        states = self._history(owned, players, start)
        profiles, committed_values, commitment_notes = commitment_schedule(owned, profile, start=start,
            quarters=horizon_quarters, rewards=self._rewards, stance=stance, overrides=overrides)
        quarter_estimates = [estimate_profile(spend) for spend in profiles]
        all_warnings.extend(commitment_notes)
        point_values = {p.slug: self._rewards.point_value_cents(p, stance=stance, overrides=overrides)
                        for p in [*candidates, *(c.product for c in owned if c.product)]}
        baseline_series, baseline_slug, baseline_fees = self._baseline(
            candidates, quarter_estimates, states, held, start, horizon_quarters, committed_values, point_values,
        )
        opened_by = {player: {c.product.slug for c in held if c.player == player} for player in players}
        steps: list[RotationStepView] = []
        cumulative: list[RotationCumulativePoint] = []
        rotation_running = baseline_running = fees_running = 0.0
        for q in range(horizon_quarters):
            estimates = quarter_estimates[q]
            quarterly_spend = round(profiles[q].monthly_total*3, 2)
            for state in states.values():
                state.as_of = add_months(start, q*3)
            quarter_start, quarter_end = add_months(start, q * 3), add_months(start, (q + 1) * 3)
            opened_by = {player: {c.product.slug for c in held if c.player == player and (c.closes is None or c.closes > quarter_start)} for player in players}
            for player, state in states.items():
                state.held_products = opened_by[player]
            choice = self._pick_card(
                candidates, estimates, players=players, states=states,
                opened_by=opened_by, quarter_index=q,
                welcome_factor=1.0 if objective in _WELCOME_OBJECTIVES else 0.0,
            )
            if choice is None:
                break
            player, product = choice
            estimate, state = estimates[product.slug], states[player]
            is_new = product.slug not in opened_by[player]
            warnings = [f"{player}: {w}" for w in evaluate_open(product, quarter_index=q, state=state)] if is_new else []
            # Rotation allocates one quarter of spending per selection. A six-
            # month offer must not count six months of spending on every card.
            reachable_this_quarter = (product.welcome_min_spend or 0) <= quarterly_spend
            welcome = estimate.welcome_value if is_new and welcome_eligible(product, state) and reachable_this_quarter else 0.0
            if is_new and not reachable_this_quarter:
                warnings.append("Bonus excluded: minimum spend exceeds the ordinary spending allocated to this quarter.")
            if is_new:
                held.append(HeldCard(player, product, quarter_start, quarter_start,
                                     add_months(quarter_start, close_after_months) if close_after_months else None))
                state.record_open(q, product)
                state.open_dates[product.slug] = quarter_start.isoformat()
                if welcome:
                    state.bonus_dates[product.slug] = quarter_end.isoformat()
            events = fee_events(held, quarter_start, quarter_end)
            rewards_due = anniversary_events(held, quarter_start, quarter_end, point_values)
            events.extend(rewards_due)
            fees = total_fees(events)
            earn, credits = round(estimate.earn_value / 4, 2), round(estimate.credits_value / 4, 2)
            earn = round(earn + committed_values[q] + sum(float(e["amount"]) for e in rewards_due), 2)
            value = round(welcome + earn + credits - fees, 2)
            all_warnings.extend(w for w in warnings if w not in all_warnings)
            steps.append(RotationStepView(
                sequence_index=q, quarter_start=quarter_start.isoformat(), quarter_label=f"Q{q + 1} · {quarter_start:%b %Y}",
                product_id=product.id, product_slug=product.slug, product_name=product.product_name,
                issuer=product.issuer, player=player,
                action="open_and_spend" if is_new else "hold", target_spend=quarterly_spend,
                projected_welcome_value=round(welcome, 2), projected_earn_value=earn,
                projected_value=value, projected_fees=fees, projected_credits=credits,
                cash_events=events, rule_warnings=warnings,
            ))
            rotation_running = round(rotation_running + value, 2)
            fees_running = round(fees_running + fees, 2)
            baseline_running = round(baseline_running + baseline_series[q], 2)
            cumulative.append(RotationCumulativePoint(
                quarter_index=q + 1, quarter_label=f"Q{q + 1}",
                rotation_cumulative_value=rotation_running, baseline_cumulative_value=baseline_running,
            ))
        lifecycle = (f"New cards close after {close_after_months} months; existing cards follow their recorded dates."
                     if close_after_months else "Retain all cards; pay opening and annual renewal fees. No unrecorded closures or downgrades assumed.")
        return RotationPlanView(
            name=name or f"{objective} ({horizon_quarters}q)", objective=objective,
            as_of_date=start.isoformat(), horizon_quarters=horizon_quarters, spend_profile=profile,
            steps=steps, projected_total_value=rotation_running, baseline_single_card_value=baseline_running,
            baseline_product_slug=baseline_slug, uplift=round(rotation_running-baseline_running, 2),
            projected_fees=fees_running, baseline_fees=baseline_fees, lifecycle=lifecycle,
            cumulative_value=cumulative, warnings=all_warnings,
            assumptions=[
                f"${profile.monthly_total:,.0f}/month in ordinary eligible planned purchases, paid in full. No extra spending to earn a bonus.",
                "Recorded owner, opening, closing and bonus history is included. Unrecorded card history and personalized offer eligibility still require verification.",
                lifecycle,
                "Full annual fees are charged on opening/renewal dates for every held card, including idle cards. Both strategies include existing household card costs.",
                "Statement credits are estimated quarterly for the spending card only; unused cards receive no assumed credits. Credits are not cash income and must replace spending already planned.",
                "A bonus counts only when the allocated quarter's ordinary spending can meet it and recorded product history permits it. Award timing is estimated within that quarter.",
                "Single-card baseline uses the same dates, recorded eligibility and full-fee convention. It includes at most one new card and one welcome bonus.",
                *(extra_assumptions or []),
            ],
        )

    @staticmethod
    def _history(cards: list[HouseholdCreditCard], players: list[str], start: date) -> dict[str, IssuerRuleState]:
        states = {player: IssuerRuleState(as_of=start) for player in players}
        for card in cards:
            if card.player not in states or card.product is None or card.status == "candidate":
                continue
            opened = parse_day(card.opened_date)
            months = (opened.year-start.year)*12 + opened.month-start.month if opened else -1
            state = states[card.player]
            state.record_open(min(-1, months // 3), card.product)
            state.open_dates[card.product.slug] = opened.isoformat() if opened else None
            if card.status in {"active", "inactive", "rotated_out"} and not card.closed_date:
                state.held_products.add(card.product.slug)
            if card.welcome_status == "earned":
                earned = card.metadata.get("welcome_earned_date")
                state.bonus_dates[card.product.slug] = str(earned) if earned else None
        return states

    @staticmethod
    def _baseline(products, quarter_estimates, states, existing, start, quarters, committed_values, point_values):
        best_series, best_slug, best_fees = [0.0] * quarters, None, 0.0
        best_total = float("-inf")
        for product in products:
            estimate = quarter_estimates[0][product.slug]
            for player, state in states.items():
                owned = next((c for c in existing if c.product.slug == product.slug and c.player == player), None)
                held = list(existing)
                if owned is None:
                    held.append(HeldCard(player, product, start, start))
                bonus = estimate.welcome_value if owned is None and welcome_eligible(product, state) else 0.0
                # Both strategies reserve only one quarter to achieve a bonus.
                if (product.welcome_min_spend or 0) > sum(c.monthly_spend for c in estimate.category_contributions) * 3:
                    bonus = 0.0
                series, fees = [], 0.0
                for q in range(quarters):
                    estimate = quarter_estimates[q][product.slug]
                    costs = total_fees(fee_events(held, add_months(start, q*3), add_months(start, (q+1)*3)))
                    fees += costs
                    active = owned is None or owned.closes is None or owned.closes > add_months(start, (q+1)*3)
                    earnings = (estimate.earn_value+estimate.credits_value)/4 if active else 0
                    earnings += sum(float(e["amount"]) for e in anniversary_events(held, add_months(start, q*3), add_months(start, (q+1)*3), point_values))
                    series.append(round(earnings + committed_values[q] - costs + (bonus if q == 0 else 0), 2))
                if sum(series) > best_total:
                    best_total, best_series, best_slug, best_fees = sum(series), series, product.slug, fees
        return best_series, best_slug, round(best_fees, 2)

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
        best_rank: tuple[float, int, int, int] | None = None
        best_choice: tuple[str, CreditCardProduct] | None = None
        for player in players:
            state = states[player]
            opens_so_far = len(opened_by[player])
            for product in candidates:
                estimate = estimates[product.slug]
                is_new_open = product.slug not in opened_by[player]
                eligible = welcome_eligible(product, state) and (product.welcome_min_spend or 0) <= sum(c.monthly_spend for c in estimate.category_contributions)*3
                welcome = estimate.welcome_value if (is_new_open and eligible) else 0.0
                score = (estimate.earn_value + estimate.credits_value) / 4.0 - (product.annual_fee if is_new_open else 0.0) + welcome_factor * welcome
                if is_new_open and evaluate_open(product, quarter_index=quarter_index, state=state):
                    score -= welcome_factor * welcome * 0.5 + CHASE_FIRST_WEIGHT
                rank = (round(score, 4), 0 if is_new_open else 1, int(product.issuer == "Chase"), -opens_so_far)
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_choice = (player, product)
        return best_choice

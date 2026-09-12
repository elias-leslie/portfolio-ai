"""Allocate ordinary purchases to unfinished owned offers before new cards."""
from __future__ import annotations

from datetime import date

from app.models.credit_cards import HouseholdCreditCard, SpendProfile
from app.services._card_rotation_cashflows import add_months, parse_day
from app.services.card_rewards_service import CardRewardsService


def commitment_schedule(cards: list[HouseholdCreditCard], profile: SpendProfile, *, start: date,
                        quarters: int, rewards: CardRewardsService, stance: str,
                        overrides: dict[str, float] | None) -> tuple[list[SpendProfile], list[float], list[str]]:
    profiles = [profile.model_copy(deep=True) for _ in range(quarters)]
    values = [0.0] * quarters
    notes: list[str] = []
    for card in sorted(cards, key=lambda c: c.welcome_deadline or '9999'):
        product = card.product
        if product is None or card.status not in {'active', 'rotated_out', 'inactive'} or card.welcome_status not in {'not_started', 'in_progress'}:
            continue
        deadline = parse_day(card.welcome_deadline)
        opened = parse_day(card.opened_date)
        if card.welcome_status == 'not_started' and (opened is None or (start-opened).days > 180) and deadline is None:
            continue  # No evidence that an old keeper has an unfinished offer.
        if deadline and deadline < start:
            continue
        if product.welcome_min_spend is None:
            # Missing original terms cannot authorize a competing new offer.
            remaining = profile.monthly_total * 3
            notes.append(f'{card.player}: confirm the original offer on {product.product_name}; first-quarter purchases are reserved until its requirement is known.')
        else:
            remaining = max(0, product.welcome_min_spend-card.welcome_progress_amount)
            if not remaining:
                continue
            notes.append(f'{card.player}: ${remaining:,.0f} reserved first for {product.product_name}' + (f' by {deadline}.' if deadline else '; deadline needs confirmation.'))
        for q in range(quarters):
            qstart, qend = add_months(start, q*3), add_months(start, (q+1)*3)
            if deadline and qstart > deadline:
                break
            days = min((qend-qstart).days, (deadline-qstart).days+1) if deadline else (qend-qstart).days
            available = profiles[q].monthly_total * 3
            allocation = min(remaining, available * max(0, days)/(qend-qstart).days)
            if allocation <= 0:
                continue
            fraction = allocation/available
            reserved = SpendProfile(monthly_total=allocation/3,
                                    by_bucket={k: v*fraction for k,v in profiles[q].by_bucket.items()})
            value = rewards.evaluate_card(product, reserved, point_value_cents=rewards.point_value_cents(product, stance=stance, overrides=overrides))
            values[q] += value.earn_value/4
            scale = (available-allocation)/available
            profiles[q] = profiles[q].model_copy(update={"monthly_total": (available-allocation)/3,
                "by_bucket": {k: v*scale for k,v in profiles[q].by_bucket.items()}})
            remaining -= allocation
            if remaining <= 0:
                # Existing rewards occur identically under both strategies.
                terms = card.metadata.get('welcome_terms')
                if isinstance(terms, dict) and terms.get('confirmed_at') and deadline:
                    values[q] += product.welcome_bonus_cash + product.welcome_bonus_points * value.assumed_point_value_cents/100
                break
        if remaining > 0:
            notes.append(f'{card.player}: ordinary purchases cannot cover ${remaining:,.0f} of the recorded welcome requirement before its deadline; do not add spending to chase it.')
    return profiles, [round(v, 2) for v in values], notes

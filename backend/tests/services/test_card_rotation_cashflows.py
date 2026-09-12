from datetime import date

from app.models.credit_cards import CreditCardProduct, HouseholdCreditCard, SpendProfile
from app.services.card_rotation_engine import CardRotationEngine


def product(slug="card", fee=500, bonus=2000):
    return CreditCardProduct(id=slug, slug=slug, issuer="Example", product_name=slug,
                             annual_fee=fee, welcome_bonus_cash=bonus, welcome_min_spend=1,
                             reward_multipliers={"other": 0})


PROFILE = SpendProfile(monthly_total=1000, by_bucket={"other": 1000})


def test_eight_openings_charge_all_fees_and_four_renewals():
    plan = CardRotationEngine().build_rotation_plan(
        [product(str(i)) for i in range(8)], PROFILE, players=["p1"],
        as_of=date(2026, 9, 11), horizon_quarters=8,
    )
    assert plan.projected_fees == 6000  # 8 x $500 openings + 4 x $500 renewals
    assert plan.projected_total_value == 10000  # 8 x $2000 bonuses - $6000
    assert plan.baseline_fees == 1000
    assert [s.projected_fees for s in plan.steps] == [500]*4 + [1000]*4
    assert sum(s.projected_value for s in plan.steps) == plan.projected_total_value
    assert plan.cumulative_value[-1].baseline_cumulative_value == plan.baseline_single_card_value


def test_short_baseline_charges_a_full_fee_and_matches_rotation():
    plan = CardRotationEngine().build_rotation_plan([product()], PROFILE, horizon_quarters=1)
    assert plan.projected_total_value == plan.baseline_single_card_value == 1500
    assert plan.uplift == 0


def test_recorded_sapphire_is_not_a_new_bonus_and_keeps_renewal_costs():
    card = product("chase-sapphire-preferred", fee=95)
    owned = HouseholdCreditCard(id="owned", product_id=card.id, product=card, player="p1",
                               status="active", opened_date="2026-07-23", welcome_status="earned")
    plan = CardRotationEngine().build_rotation_plan(
        [card], PROFILE, players=["p1"], owned_cards=[owned],
        as_of=date(2026, 9, 11), horizon_quarters=8,
    )
    assert all(s.projected_welcome_value == 0 and s.action == "hold" for s in plan.steps)
    assert plan.projected_fees == plan.baseline_fees == 190
    dates = [e["date"] for s in plan.steps for e in s.cash_events]
    assert dates == ["2027-07-23", "2028-07-23"]


def test_six_month_bonus_does_not_double_count_next_quarters_spend():
    card = product()
    card.welcome_min_spend = 5000
    card.welcome_window_days = 180
    plan = CardRotationEngine().build_rotation_plan([card], PROFILE, horizon_quarters=1)
    assert plan.steps[0].projected_welcome_value == 0
    assert plan.baseline_single_card_value == -500


def test_idle_owned_card_fee_is_in_both_comparisons():
    keeper = product("keeper", fee=95, bonus=0)
    owned = HouseholdCreditCard(id="keeper", product_id=keeper.id, product=keeper, player="p2",
                               status="active", opened_date="2025-10-01", role="keeper")
    plan = CardRotationEngine().build_rotation_plan(
        [product()], PROFILE, owned_cards=[owned], as_of=date(2026, 9, 11), horizon_quarters=1,
    )
    assert plan.projected_fees == plan.baseline_fees == 595
    assert plan.projected_total_value == plan.baseline_single_card_value == 1405


def test_existing_welcome_spend_reservation_expires_and_is_shared_by_baseline():
    held = product('owned', fee=0, bonus=500)
    held.welcome_min_spend = 3000
    held.reward_multipliers = {'other': 1}
    owned = HouseholdCreditCard(id='owned', product_id=held.id, product=held,
        status='active', opened_date='2026-08-01', welcome_deadline='2026-11-01',
        welcome_status='in_progress', welcome_progress_amount=2000,
        metadata={'welcome_terms':{'confirmed_at':'2026-08-01'}})
    plan = CardRotationEngine().build_rotation_plan([product(fee=0)], PROFILE, owned_cards=[owned],
        as_of=date(2026,9,11), horizon_quarters=2, players=['p1'])
    assert plan.steps[0].target_spend == 2000
    assert plan.steps[1].target_spend == 3000
    assert plan.steps[0].projected_earn_value == 510  # original bonus plus $10 normal earn


def test_anniversary_miles_arrive_after_first_year_and_are_not_prorated():
    card = product(fee=0, bonus=0)
    card.issuer_rules = {'anniversary_points':10000}
    plan = CardRotationEngine().build_rotation_plan([card], PROFILE, as_of=date(2026,9,11), horizon_quarters=5, players=['p1'])
    assert [s.projected_earn_value for s in plan.steps] == [0,0,0,0,100]
    assert plan.projected_total_value == plan.baseline_single_card_value == 100


def test_old_keeper_without_an_open_offer_does_not_reserve_new_spending():
    keeper = product('keeper', fee=0, bonus=0)
    keeper.welcome_min_spend = None
    owned = HouseholdCreditCard(id='keeper',product_id=keeper.id,product=keeper,status='active',role='keeper')
    plan = CardRotationEngine().build_rotation_plan([product(fee=0)], PROFILE, owned_cards=[owned], horizon_quarters=1)
    assert plan.steps[0].target_spend == 3000
    assert not any('confirm the original offer' in w for w in plan.warnings)


def test_zero_spending_never_opens_a_card_for_a_fictional_chase_score():
    card = product('held',fee=95,bonus=0)
    card.issuer = 'Chase'
    owned = HouseholdCreditCard(id='held',product_id=card.id,product=card,status='active',welcome_status='earned',opened_date='2025-01-01')
    free = product('free',fee=0,bonus=200)
    free.issuer = 'Chase'
    free.welcome_min_spend = 500
    plan = CardRotationEngine().build_rotation_plan([card,free],SpendProfile(monthly_total=0,by_bucket={}),owned_cards=[owned],horizon_quarters=1)
    assert plan.steps[0].action == 'hold'

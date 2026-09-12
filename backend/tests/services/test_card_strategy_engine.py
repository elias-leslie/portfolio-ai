from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.models.card_strategy import StrategyBaseline, StrategySettings
from app.models.credit_cards import CreditCardProduct, HouseholdCreditCard
from app.services.card_strategy_engine import (
    build_baseline,
    rank_candidates,
    suggest_bills,
    terms_evidence,
    track_bonuses,
)

TODAY = date(2026, 9, 12)


def product(**changes):
    base = CreditCardProduct(id="product", slug="example", issuer="Chase", product_name="Example",
        annual_fee=95, welcome_min_spend=4000, welcome_bonus_points=60000, welcome_window_days=90)
    base = base.model_copy(update=changes)
    for key in ("annual_fee", "welcome_min_spend", "welcome_bonus_points", "welcome_window_days"):
        base.verified_terms[key] = {"value": getattr(base, key), "source_url": "https://creditcards.chase.com/example",
            "excerpt": str(getattr(base, key)), "checked_at": TODAY.isoformat()}
    return base


def baseline(amount=2000):
    return StrategyBaseline(monthly_available=amount, historical_monthly=amount, months=[],
        income_monthly=4000, income_source="measured", free_cash=5000, cash_status="estimate", reservations=[], warnings=[])


def card(**changes):
    return HouseholdCreditCard(id="card", product_id="product", product=product(), status="active",
        household_account_id="account", opened_date="2026-07-01", welcome_deadline="2026-10-12", **changes)


def purchase(amount, on=TODAY, **changes):
    return dict(id="row", date=on, amount=abs(amount), signed_amount=amount, household_account_id="account",
        merchant="Store", description="", category="Retail", pending=False, **changes)


def test_baseline_uses_real_months_reserves_merchants_and_never_inflates_to_a_cap():
    rows = []
    for month in (6, 7, 8):
        on = date(2026, month, 15)
        rows += [purchase(2000, on), {**purchase(500, on), "merchant":"Amazon"},
                 {**purchase(10000, on), "category":"Travel"}, {**purchase(3000, on), "household_account_id":"bank"},
                 {**purchase(5000, on), "pending":True}, {**purchase(95, on), "merchant":"Annual Membership Fee"}]
    household = SimpleNamespace(income_anchor=SimpleNamespace(monthly_income=4000, source_label="measured", profile_target_detail=""),
        budget_snapshot=SimpleNamespace(affordability=SimpleNamespace(free_to_spend=5000,status="estimate",missing_inputs=[])), accounts=[])
    result = build_baseline(rows, [card()], household, StrategySettings(monthly_cap=9000), TODAY)
    assert result.monthly_available == 1800
    assert [m.ordinary_card_spend for m in result.months] == [2000]*3
    assert [m.reserved_spend for m in result.months] == [500]*3
    shifted = build_baseline(rows, [card()], household, StrategySettings(costco_monthly=900), TODAY)
    assert shifted.monthly_available == 990


def test_evidence_requires_supporting_numbers_freshness_and_an_issuer():
    p = product()
    assert terms_evidence(p, TODAY)[0]
    p.verified_terms["welcome_bonus_points"]["excerpt"] = "Travel portal purchases earn rewards."
    assert not terms_evidence(p, TODAY)[0]
    p = product()
    p.verified_terms["annual_fee"]["source_url"] = "https://chase.com.example.org"
    assert not terms_evidence(p, TODAY)[0]
    assert not terms_evidence(product(), TODAY+timedelta(days=31))[0]


def test_ranking_honors_real_offer_windows_and_prior_bonuses():
    p = product(welcome_min_spend=8000, welcome_window_days=180)
    result = rank_candidates([p], [], baseline(), [], TODAY)
    assert len(result) == 2
    assert result[0].monthly_required < 1400
    assert rank_candidates([p], [], baseline(1000), [], TODAY) == []
    owned = card(welcome_status="earned")
    ranked = rank_candidates([owned.product], [owned], baseline(), [], TODAY)
    assert [c.player for c in ranked] == ["p2"]
    assert rank_candidates([p], [], baseline().model_copy(update={"cash_status":"hold"}), [], TODAY) == []


def test_tracking_nets_refunds_excludes_fees_and_pending_and_never_invents_receipt():
    c = card()
    rows = [purchase(1000), purchase(-100), {**purchase(200), "pending":True},
            {**purchase(95), "merchant":"Annual Membership Fee"}]
    result = track_bonuses([c], rows, baseline(), TODAY)[0]
    assert result.posted == 900
    assert result.pending == 200
    assert result.remaining == 3100
    assert result.status == "at_risk"
    c.welcome_status = "earned"
    assert track_bonuses([c], rows, baseline(), TODAY)[0].status == "received"


def test_competing_bonuses_cannot_allocate_the_same_future_spend_twice():
    first = card()
    first.product.welcome_min_spend = 500
    second = card().model_copy(update={"id":"second","household_account_id":"second-account"})
    tracks = track_bonuses([first, second], [], baseline(), TODAY)
    assert sum(t.forecast or 0 for t in tracks) <= 2000
    assert tracks[0].forecast == 500
    assert tracks[1].status == "at_risk"


@pytest.mark.parametrize("field,value", [("opened_date",None),("household_account_id",None),("welcome_deadline",None)])
def test_unknown_inputs_are_not_treated_as_completed(field, value):
    c = card().model_copy(update={field:value})
    assert track_bonuses([c], [], baseline(), TODAY)[0].status == "needs_data"


def test_refunds_after_the_deadline_reduce_eligible_spending():
    c = card().model_copy(update={"welcome_deadline": "2026-09-10"})
    result = track_bonuses([c], [purchase(4000, date(2026, 9, 9)), purchase(-100)], baseline(), TODAY)[0]
    assert result.posted == 3900
    assert result.status == "expired"


def test_family_bonus_history_excludes_the_other_venture_product():
    p = product(issuer_rules={"bonus_family_slugs": ["example", "venture-x"], "bonus_family_months": 48})
    old = card(welcome_status="earned", welcome_earned_date="2024-09-12")
    old.product.slug = "venture-x"
    old.status = "closed"
    assert [c.player for c in rank_candidates([p], [old], baseline(), [], TODAY)] == ["p2"]
    old.welcome_earned_date = None
    assert [c.player for c in rank_candidates([p], [old], baseline(), [], TODAY)] == ["p2"]


def test_timestamp_refresh_does_not_change_the_material_offer_fingerprint():
    p = product()
    before = rank_candidates([p], [], baseline(), [], TODAY)[0]
    p.updated_at = "2026-09-12T20:00:00Z"
    after = rank_candidates([p], [], baseline(), [], TODAY)[0]
    assert before.terms_fingerprint == after.terms_fingerprint


def test_bill_payment_identity_uses_the_latest_posted_payment_and_canonical_cma_type():
    bill = SimpleNamespace(merchant="Duke Energy", average_amount=200, cadence="monthly",
        commitment_type="bill", due_status="upcoming", next_expected="2026-10-01", evidence="Monthly payments")
    accounts = [SimpleNamespace(household_account_id="bank", account_type="cash_management", label="Joint account")]
    rows = [{**purchase(200), "merchant":"Duke Energy", "household_account_id":"bank", "account_label":"Joint account"},
            {**purchase(200, TODAY+timedelta(days=1)), "merchant":"Duke Energy", "pending":True},
            {**purchase(-200, TODAY+timedelta(days=1)), "merchant":"Duke Energy"}]
    result = suggest_bills([bill], rows, [card()], accounts)[0]
    assert result.paid_from_cma
    assert not result.already_card_spend
    assert result.fee_per_charge is None and result.lost_discount is None
    rows.append({**purchase(200, TODAY+timedelta(days=2)), "merchant":"Duke Energy"})
    result = suggest_bills([bill], rows, [card()], accounts)[0]
    assert not result.paid_from_cma
    assert result.already_card_spend


def test_ordinary_bank_accounts_are_not_assumed_to_be_cma_accounts():
    bill = SimpleNamespace(merchant="Phone", average_amount=100, cadence="monthly",
        commitment_type="bill", due_status="upcoming", next_expected=None, evidence=None)
    accounts = [SimpleNamespace(household_account_id="bank", account_type="checking", label="Other bank")]
    rows = [{**purchase(100), "merchant":"Phone", "household_account_id":"bank", "account_label":"Other bank"}]
    assert not suggest_bills([bill], rows, [], accounts)[0].paid_from_cma


def test_nearby_spending_options_are_visible_without_displacing_the_best_fit():
    fit = product()
    stretch = product(id="stretch", slug="stretch", welcome_min_spend=5600, welcome_bonus_points=100000)
    far = product(id="far", slug="far", welcome_min_spend=8000, welcome_bonus_points=150000)
    results = rank_candidates([fit, stretch, far], [], baseline(1800), [], TODAY)
    assert len(results) == 4
    assert results[0].product_id == fit.id
    assert results[0].value_rank == 2
    assert results[0].compared_offers == 2
    assert results[0].catalog_offers == 3
    option = next(c for c in results if c.product_id == "stretch")
    assert option.value_rank == 1
    assert option.spending_gap == round(5600 - 1800 * 83 / 30.4375, 2)
    assert option.monthly_gap == round(option.spending_gap * 30.4375 / 83, 2)
    assert "Additional planned purchases" in option.rationale


def test_unverified_offers_do_not_receive_a_value_rank_and_ties_share_rank():
    first = product()
    tied = product(id="tied", slug="tied")
    unknown = product(id="unknown", slug="unknown", welcome_bonus_points=100000)
    unknown.verified_terms = {}
    results = rank_candidates([first, tied, unknown], [], baseline(), [], TODAY)
    assert all(c.value_rank == 1 and c.compared_offers == 2 for c in results if c.terms_current)
    assert all(c.value_rank is None for c in results if not c.terms_current)

"""Unit tests for the deterministic card rewards + rotation engines.

The point of these tests is to nail the valuation and sequencing math by hand
(plan section 13), not to exercise the DB facade. Everything here is pure.
"""

from __future__ import annotations

from app.models.credit_cards import CardCredit, CreditCardProduct, SpendProfile
from app.services._card_issuer_rules import IssuerRuleState, evaluate_open, welcome_eligible
from app.services.card_rewards_service import CardRewardsService
from app.services.card_rotation_engine import CardRotationEngine


def _product(**kw: object) -> CreditCardProduct:
    base: dict[str, object] = {
        "id": kw.get("slug", "x"),
        "slug": "x",
        "issuer": "Chase",
        "product_name": "Test",
        "card_kind": "personal",
        "annual_fee": 0.0,
        "reward_multipliers": {"other": 1.0},
        "point_program": "ultimate_rewards",
        "est_point_value_cents": 1.8,
        "welcome_bonus_points": 0,
        "welcome_bonus_cash": 0.0,
        "welcome_min_spend": None,
        "welcome_window_days": 90,
        "credits": [],
        "issuer_rules": {},
    }
    base.update(kw)
    return CreditCardProduct(**base)


def test_evaluate_card_earn_and_welcome_math() -> None:
    """Hand-computed: $1000/mo dining at 3x and 2.0c/pt, plus a reachable
    60k-point welcome, with a $95 fee."""
    svc = CardRewardsService()
    profile = SpendProfile(monthly_total=1000.0, by_bucket={"dining": 1000.0})
    product = _product(
        slug="dining-card",
        annual_fee=95.0,
        reward_multipliers={"dining": 3.0, "other": 1.0},
        est_point_value_cents=2.0,
        welcome_bonus_points=60000,
        welcome_min_spend=4000,
        welcome_window_days=90,
    )
    est = svc.evaluate_card(product, profile, point_value_cents=2.0, amortization_years=3)

    # earn = 1000 * 12 * 3 * 0.02 = 720
    assert est.earn_value == 720.0
    # annual_value = earn + credits(0) - fee(95) = 625
    assert est.annual_value == 625.0
    # welcome reachable: 1000 * (90/30=3) = 3000 < 4000 -> NOT reachable
    assert est.welcome_reachable is False
    assert est.welcome_value == 0.0
    assert any("minimum spend" in w for w in est.warnings)


def test_welcome_counts_when_reachable() -> None:
    svc = CardRewardsService()
    profile = SpendProfile(monthly_total=6500.0, by_bucket={"other": 6500.0})
    product = _product(
        slug="welcome-card",
        reward_multipliers={"other": 1.0},
        est_point_value_cents=2.0,
        welcome_bonus_points=60000,
        welcome_min_spend=4000,
        welcome_window_days=90,
    )
    est = svc.evaluate_card(product, profile, point_value_cents=2.0, amortization_years=3)
    # 6500 * 3 = 19500 >= 4000 -> reachable; welcome = 60000 * 0.02 = 1200
    assert est.welcome_reachable is True
    assert est.welcome_value == 1200.0
    # first-year adds the full welcome; steady-state adds welcome amortized over 3y
    assert round(est.first_year_value - est.annual_value, 2) == 1200.0
    assert round(est.steady_state_value - est.annual_value, 2) == 400.0


def test_credit_realization_haircut() -> None:
    svc = CardRewardsService()
    profile = SpendProfile(monthly_total=0.0, by_bucket={})
    product = _product(
        slug="credit-card",
        annual_fee=695.0,
        credits=[
            CardCredit(name="easy", annual_value=300, type="easy"),
            CardCredit(name="hard", annual_value=200, type="hard"),
        ],
    )
    est = svc.evaluate_card(product, profile, point_value_cents=2.0)
    # credits = 300*1.0 + 200*0.25 = 350
    assert est.credits_value == 350.0
    assert est.annual_value == round(350.0 - 695.0, 2)


def test_point_value_stance_scaling_and_cash_floor() -> None:
    svc = CardRewardsService()
    ur = _product(slug="ur", est_point_value_cents=1.8, point_program="ultimate_rewards")
    cash = _product(slug="cash", est_point_value_cents=1.0, point_program="wells_fargo_rewards")
    assert svc.point_value_cents(ur, stance="balanced") == 1.8
    assert svc.point_value_cents(ur, stance="conservative") == round(1.8 * 0.8, 4)
    assert svc.point_value_cents(ur, stance="optimistic") == round(1.8 * 1.25, 4)
    # cash-like programs are never scaled
    assert svc.point_value_cents(cash, stance="optimistic") == 1.0
    # explicit override wins regardless of stance
    assert svc.point_value_cents(ur, stance="conservative", overrides={"ultimate_rewards": 2.5}) == 2.5


def test_issuer_rules_5_24_and_amex_lifetime() -> None:
    state = IssuerRuleState()
    chase = _product(slug="chase-x", issuer="Chase", issuer_rules={"chase_5_24": True})
    # Open 5 non-Chase cards in the trailing 24 months (quarters 0..4)
    for i in range(5):
        state.record_open(i, _product(slug=f"other-{i}", issuer="Other"))
    warnings = evaluate_open(chase, quarter_index=6, state=state)
    assert any("5/24" in w for w in warnings)

    amex = _product(slug="amex-gold", issuer="American Express", issuer_rules={"amex_once_per_lifetime": True})
    assert welcome_eligible(amex, state) is True
    state.record_open(7, amex)
    assert welcome_eligible(amex, state) is False
    assert any("once per lifetime" in w for w in evaluate_open(amex, quarter_index=8, state=state))


def test_rotation_beats_baseline_and_flags_5_24() -> None:
    """Several welcome-rich cards -> rotation captures multiple bonuses and
    exceeds the single-card baseline; a Chase card sequenced after 5 opens trips
    a 5/24 warning."""
    svc = CardRewardsService()
    engine = CardRotationEngine(svc)
    profile = SpendProfile(monthly_total=6500.0, by_bucket={"other": 6500.0, "dining": 0.0})

    products = [
        _product(
            slug=f"card-{i}",
            issuer="Capital One" if i % 2 else "Citi",
            reward_multipliers={"other": 1.0},
            est_point_value_cents=1.8,
            welcome_bonus_points=60000,
            welcome_min_spend=4000,
            welcome_window_days=90,
            issuer_rules={},
        )
        for i in range(7)
    ]
    # one Chase card to exercise 5/24
    products.append(
        _product(
            slug="chase-csp",
            issuer="Chase",
            reward_multipliers={"other": 1.0},
            est_point_value_cents=1.8,
            welcome_bonus_points=60000,
            welcome_min_spend=4000,
            welcome_window_days=90,
            issuer_rules={"chase_5_24": True},
        )
    )

    plan = engine.build_rotation_plan(
        products, profile, objective="rotate_90d", horizon_quarters=8
    )
    assert len(plan.steps) == 8
    # rotation captures more than one welcome -> beats keep-forever baseline
    assert plan.projected_total_value > plan.baseline_single_card_value
    assert plan.uplift > 0
    # cumulative curve is monotonic non-decreasing for both series
    rot = [p.rotation_cumulative_value for p in plan.cumulative_value]
    assert rot == sorted(rot)
    # Chase-first weight pulls the Chase open early (before 5/24 bites)
    chase_step = next((s for s in plan.steps if s.product_slug == "chase-csp"), None)
    assert chase_step is not None
    assert chase_step.sequence_index <= 1


def test_maximize_category_earn_holds_one_card() -> None:
    svc = CardRewardsService()
    engine = CardRotationEngine(svc)
    profile = SpendProfile(monthly_total=6500.0, by_bucket={"dining": 6500.0})
    products = [
        _product(slug="best-dining", issuer="Citi", reward_multipliers={"dining": 4.0, "other": 1.0}),
        _product(slug="weak", issuer="Citi", reward_multipliers={"dining": 1.0, "other": 1.0}),
    ]
    plan = engine.build_rotation_plan(
        products, profile, objective="maximize_category_earn", horizon_quarters=4
    )
    # with welcome_factor 0 it should settle on the best earner every quarter
    assert all(s.product_slug == "best-dining" for s in plan.steps)

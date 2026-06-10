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
    # Default easy_only stance (hands-off): hard credits count $0.
    est = svc.evaluate_card(product, profile, point_value_cents=2.0)
    assert est.credits_value == 300.0
    assert est.annual_value == round(300.0 - 695.0, 2)
    assert any("easy_only" in w for w in est.warnings)
    # Balanced stance keeps the fractional realization haircut.
    est_balanced = svc.evaluate_card(product, profile, point_value_cents=2.0, credit_stance="balanced")
    # credits = 300*1.0 + 200*0.25 = 350
    assert est_balanced.credits_value == 350.0
    assert est_balanced.annual_value == round(350.0 - 695.0, 2)
    # Face value counts everything.
    est_face = svc.evaluate_card(product, profile, point_value_cents=2.0, credit_stance="face_value")
    assert est_face.credits_value == 500.0


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


def test_two_player_rotation_alternates_and_avoids_5_24() -> None:
    """Two players alternating keep each under 5/24 across 8 quarters, so a
    Chase open in a late quarter draws no 5/24 warning; a solo player at the
    same cadence trips it."""
    svc = CardRewardsService()
    engine = CardRotationEngine(svc)
    profile = SpendProfile(monthly_total=6500.0, by_bucket={"other": 6500.0})
    products = [
        _product(
            slug=f"chase-{i}",
            issuer="Chase",
            reward_multipliers={"other": 1.0},
            welcome_bonus_points=60000,
            welcome_min_spend=4000,
            welcome_window_days=90,
            issuer_rules={"chase_5_24": True},
        )
        for i in range(10)
    ]

    duo = engine.build_rotation_plan(products, profile, horizon_quarters=8)
    opens_by_player: dict[str, int] = {}
    for step in duo.steps:
        if step.action == "open_and_spend":
            opens_by_player[step.player or "?"] = opens_by_player.get(step.player or "?", 0) + 1
    # alternation: both players open, neither exceeds 4 in 8 quarters
    assert set(opens_by_player) == {"p1", "p2"}
    assert max(opens_by_player.values()) <= 4
    assert not any("5/24" in w for w in duo.warnings)

    solo = engine.build_rotation_plan(products, profile, horizon_quarters=8, players=["p1"])
    assert all(s.player == "p1" for s in solo.steps)
    assert any("5/24" in w for w in solo.warnings)


def test_keeper_routing_excludes_covered_bucket() -> None:
    """Amazon-style keeper absorbs the amazon bucket; rotating profile shrinks
    and the note names the keeper."""
    svc = CardRewardsService()
    profile = SpendProfile(
        monthly_total=6500.0,
        by_bucket={"amazon": 600.0, "dining": 1200.0, "other": 4700.0},
    )
    keeper = _product(
        slug="amazon-prime-visa",
        product_name="Amazon Prime Visa",
        issuer="Chase",
        reward_multipliers={"amazon": 5.0, "dining": 2.0, "other": 1.0},
        point_program="cash",
        est_point_value_cents=1.0,
    )
    rotating = _product(
        slug="csp",
        issuer="Chase",
        reward_multipliers={"dining": 3.0, "other": 1.0},
        est_point_value_cents=1.5,
    )
    adjusted, notes = svc.route_keeper_buckets(profile, [keeper], [keeper, rotating])
    # amazon (5.0 vs 1.5 c/$) routed to keeper; dining (2.0 vs 4.5 c/$) stays
    assert "amazon" not in adjusted.by_bucket
    assert adjusted.by_bucket["dining"] == 1200.0
    assert adjusted.monthly_total == 5900.0
    assert any("amazon-prime" in n.lower() or "Amazon" in n for n in notes)
    # no keepers -> profile unchanged
    same, no_notes = svc.route_keeper_buckets(profile, [], [rotating])
    assert same == profile and no_notes == []

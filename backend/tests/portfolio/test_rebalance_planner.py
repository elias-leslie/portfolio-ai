"""Tests for RebalancePlanner — the three-pass tax-aware planner.

Verifies:

1. Buys route to tax-advantaged accounts when ``prefer_tax_advantaged``.
2. Taxable sells prefer LT-loss / LT-gain over ST-gain (TLH-aware
   ranking via :func:`_rank_priority`).
3. Wash-sale conflicts on a taxable sell trigger reroute to a
   tax-advantaged sibling, OR a flagged trade with the conflicting buy
   reference.

The TLHAnalyzer is mocked at the wash_sale_check seam so the planner
test stays focused on planner behavior, not TLH analytics. The lot
ranking helpers are also tested directly.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.portfolio.asset_classification import AssetClassifier
from app.portfolio.contracts.tlh import WashSaleVerdict
from app.portfolio.ips import (
    RATIONALE_AVOID_REALIZE_GAIN,
    RATIONALE_LT_GAIN_OVER_ST,
    RATIONALE_LT_LOSS_FIRST,
    RATIONALE_ROUTE_TO_TAX_ADVANTAGED,
    RATIONALE_ROUTE_TO_TAXABLE,
    RATIONALE_WASH_SALE_BLOCKED,
    RATIONALE_WASH_SALE_REROUTED,
    DriftCalculator,
    IPSService,
    RebalancePlanner,
    _Holding,
    _make_sell_candidate,
    _rank_priority,
)
from app.portfolio.models import PriceData
from tests.portfolio.test_ips import _FakePriceFetcher, _FakeStorage


def _ledger_returning_lots(lots_by_position: dict[tuple[str, str], list[Any]]) -> MagicMock:
    """Build a ledger mock that returns canned lots and FIFO results."""
    ledger = MagicMock()
    ledger.open_lots.side_effect = lambda account_id, symbol: lots_by_position.get(
        (account_id, symbol), []
    )

    def _consume(*, account_id: str, symbol: str, shares: float, sell_date: date, sell_price: float) -> Any:
        consume = MagicMock()
        consume.realized_gain_long_term = 0.0
        consume.realized_gain_short_term = 0.0
        consume.used_position_aggregate_fallback = not lots_by_position.get((account_id, symbol))
        return consume

    ledger.consume_lots_fifo.side_effect = _consume
    return ledger


def _build_planner(
    *,
    accounts: list[tuple[str, str]],
    targets: list[tuple[str, float, float]],
    positions: list[tuple[str, str, float, float]],
    prices: dict[str, float],
    wash_sale_verdict: WashSaleVerdict | None = None,
    ledger: MagicMock | None = None,
) -> RebalancePlanner:
    storage = _FakeStorage()
    store = storage.store
    for acct_id, acct_type in accounts:
        store.add_account(id=acct_id, account_type=acct_type)
    for acct_id, symbol, shares, cost in positions:
        store.add_position(account_id=acct_id, symbol=symbol, shares=shares, cost_basis=cost)

    ips = IPSService(storage)
    for asset_class, target_pct, band in targets:
        ips.set_target(
            scope="household",
            scope_id="hh1",
            asset_class=asset_class,
            target_pct=target_pct,
            drift_band_pct=band,
        )

    classifier = AssetClassifier(storage=None)
    fetcher = _FakePriceFetcher(prices)
    drift_calc = DriftCalculator(storage, classifier, ips, fetcher)

    tlh_analyzer = MagicMock()
    tlh_analyzer.wash_sale_check.return_value = wash_sale_verdict or WashSaleVerdict(
        symbol="X",
        sell_date=date.today(),
        household_id="hh1",
        blocked=False,
    )
    if ledger is None:
        ledger = _ledger_returning_lots({})
    planner = RebalancePlanner(drift_calc, tlh_analyzer, ledger)
    return planner


# ----------------------------------------------------------------------
# rank_priority — pure unit
# ----------------------------------------------------------------------


def test_rank_priority_lt_loss_beats_everything() -> None:
    rationale, priority = _rank_priority(is_long_term=True, is_loss=True, prefer_ltcg=True)
    assert rationale == RATIONALE_LT_LOSS_FIRST
    assert priority == 10


def test_rank_priority_st_loss_second() -> None:
    _rationale, priority = _rank_priority(is_long_term=False, is_loss=True, prefer_ltcg=True)
    assert priority == 20


def test_rank_priority_lt_gain_third() -> None:
    rationale, priority = _rank_priority(is_long_term=True, is_loss=False, prefer_ltcg=True)
    assert rationale == RATIONALE_LT_GAIN_OVER_ST
    assert priority == 30


def test_rank_priority_st_gain_last() -> None:
    rationale, priority = _rank_priority(is_long_term=False, is_loss=False, prefer_ltcg=True)
    assert rationale == RATIONALE_AVOID_REALIZE_GAIN
    assert priority == 40


def test_rank_priority_lt_gain_falls_back_when_prefer_ltcg_off() -> None:
    rationale, _ = _rank_priority(is_long_term=True, is_loss=False, prefer_ltcg=False)
    assert rationale == RATIONALE_AVOID_REALIZE_GAIN


# ----------------------------------------------------------------------
# make_sell_candidate
# ----------------------------------------------------------------------


def test_make_sell_candidate_marks_loss_and_long_term() -> None:
    holding = _Holding(
        account_id="acct-tax",
        account_type="Taxable",
        symbol="VTI",
        shares=10,
        cost_per_share=200.0,
        current_value=1500.0,  # $150/share — loss
    )
    old_lot = MagicMock()
    old_lot.acquired_date = date(2020, 1, 1)
    old_lot.remaining_shares = 10
    ledger = MagicMock()
    ledger.open_lots.return_value = [old_lot]
    candidate = _make_sell_candidate(holding, ledger, prefer_ltcg=True)
    assert candidate.is_loss is True
    assert candidate.is_long_term is True
    assert candidate.rationale == RATIONALE_LT_LOSS_FIRST


def test_make_sell_candidate_no_lots_treats_as_short_term() -> None:
    holding = _Holding(
        account_id="acct-tax",
        account_type="Taxable",
        symbol="VTI",
        shares=10,
        cost_per_share=100.0,
        current_value=1200.0,  # gain
    )
    ledger = MagicMock()
    ledger.open_lots.return_value = []
    candidate = _make_sell_candidate(holding, ledger, prefer_ltcg=True)
    assert candidate.is_loss is False
    assert candidate.is_long_term is False
    assert candidate.rationale == RATIONALE_AVOID_REALIZE_GAIN


# ----------------------------------------------------------------------
# RebalancePlanner.propose_trades — integration via DriftCalculator
# ----------------------------------------------------------------------


def test_buy_routes_to_tax_advantaged_when_underweight() -> None:
    planner = _build_planner(
        accounts=[("roth", "Roth"), ("tax", "Taxable")],
        targets=[("us_equity", 0.5, 0.05), ("bonds", 0.5, 0.05)],
        # 100% bonds — drift wants buys for us_equity
        positions=[("tax", "BND", 100.0, 100.0)],
        prices={"BND": 100.0},
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    buys = [t for t in plan.trades if t.action == "buy"]
    assert len(buys) == 1
    assert buys[0].account_id == "roth"
    assert buys[0].account_type == "Roth"
    assert buys[0].asset_class == "us_equity"
    assert buys[0].rationale == RATIONALE_ROUTE_TO_TAX_ADVANTAGED


def test_buy_routes_to_taxable_when_no_tax_advantaged_account() -> None:
    planner = _build_planner(
        accounts=[("tax", "Taxable")],
        targets=[("us_equity", 0.5, 0.05), ("bonds", 0.5, 0.05)],
        positions=[("tax", "BND", 100.0, 100.0)],
        prices={"BND": 100.0},
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    buys = [t for t in plan.trades if t.action == "buy"]
    assert buys[0].account_type == "Taxable"
    assert buys[0].rationale == RATIONALE_ROUTE_TO_TAXABLE


def test_overweight_class_triggers_sell_with_lt_loss_priority() -> None:
    # Holding at $50 from $100 cost = LT loss (oldest lot from 2020).
    old_lot = MagicMock()
    old_lot.acquired_date = date(2020, 1, 1)
    old_lot.remaining_shares = 100
    ledger = _ledger_returning_lots({("tax", "VTI"): [old_lot]})

    planner = _build_planner(
        accounts=[("tax", "Taxable")],
        targets=[("us_equity", 0.0, 0.05), ("bonds", 1.0, 0.05)],
        positions=[("tax", "VTI", 100.0, 100.0), ("tax", "BND", 50.0, 100.0)],
        prices={"VTI": 50.0, "BND": 100.0},  # VTI overweight even though loss
        ledger=ledger,
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    sells = [t for t in plan.trades if t.action == "sell"]
    assert sells, "expected a sell trade for overweight us_equity"
    assert sells[0].symbol == "VTI"
    assert sells[0].rationale == RATIONALE_LT_LOSS_FIRST


def test_wash_sale_conflict_reroutes_to_tax_advantaged_sibling() -> None:
    # Two accounts hold VTI; taxable sale would trigger wash-sale block;
    # planner should reroute sell to Roth.
    blocking_verdict = WashSaleVerdict(
        symbol="VTI",
        sell_date=date(2026, 5, 9),
        household_id="hh1",
        blocked=True,
        reason="conflict in spouse Roth",
    )
    planner = _build_planner(
        accounts=[("tax", "Taxable"), ("roth", "Roth")],
        targets=[("us_equity", 0.0, 0.05), ("bonds", 1.0, 0.05)],
        positions=[
            ("tax", "VTI", 100.0, 100.0),
            ("roth", "VTI", 50.0, 100.0),
            ("tax", "BND", 50.0, 100.0),
        ],
        prices={"VTI": 100.0, "BND": 100.0},
        wash_sale_verdict=blocking_verdict,
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    sells = [t for t in plan.trades if t.action == "sell"]
    assert sells, "expected a sell trade"
    assert sells[0].account_type == "Roth"
    assert sells[0].rationale == RATIONALE_WASH_SALE_REROUTED
    assert sells[0].wash_sale_conflict is False  # rerouted, not blocked


def test_wash_sale_conflict_flags_when_no_reroute_target() -> None:
    blocking_verdict = WashSaleVerdict(
        symbol="VTI",
        sell_date=date(2026, 5, 9),
        household_id="hh1",
        blocked=True,
        reason="conflict in spouse Roth",
    )
    # Only one taxable account — no tax-advantaged sibling to reroute to.
    planner = _build_planner(
        accounts=[("tax", "Taxable")],
        targets=[("us_equity", 0.0, 0.05), ("bonds", 1.0, 0.05)],
        positions=[("tax", "VTI", 100.0, 100.0), ("tax", "BND", 50.0, 100.0)],
        prices={"VTI": 100.0, "BND": 100.0},
        wash_sale_verdict=blocking_verdict,
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    sells = [t for t in plan.trades if t.action == "sell"]
    assert sells[0].wash_sale_conflict is True
    assert sells[0].rationale == RATIONALE_WASH_SALE_BLOCKED
    assert sells[0].wash_sale_reason == "conflict in spouse Roth"
    assert plan.wash_sale_conflicts == 1


def test_buy_populates_shares_from_quoted_price_when_unheld() -> None:
    planner = _build_planner(
        accounts=[("roth", "Roth"), ("tax", "Taxable")],
        targets=[("us_equity", 0.5, 0.05), ("bonds", 0.5, 0.05)],
        # 100% bonds at $10k — half should be bought as VTI, $5k worth.
        positions=[("tax", "BND", 100.0, 100.0)],
        # VTI is *not* held; price is published so the planner can size shares.
        prices={"BND": 100.0, "VTI": 200.0},
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    buys = [t for t in plan.trades if t.action == "buy"]
    assert len(buys) == 1
    assert buys[0].symbol == "VTI"
    assert buys[0].estimated_value == 5000.0
    # 5000 / 200 = 25.0 shares.
    assert buys[0].shares == 25.0


def test_buy_falls_back_to_zero_shares_when_quote_missing() -> None:
    planner = _build_planner(
        accounts=[("roth", "Roth"), ("tax", "Taxable")],
        targets=[("us_equity", 0.5, 0.05), ("bonds", 0.5, 0.05)],
        positions=[("tax", "BND", 100.0, 100.0)],
        # No VTI price — planner should still emit the trade with the
        # estimated_value populated and fall back to shares=0 so the
        # contract stays stable.
        prices={"BND": 100.0},
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    buys = [t for t in plan.trades if t.action == "buy"]
    assert len(buys) == 1
    assert buys[0].symbol == "VTI"
    assert buys[0].shares == 0.0
    assert buys[0].estimated_value == 5000.0


def test_balanced_portfolio_proposes_no_trades() -> None:
    planner = _build_planner(
        accounts=[("tax", "Taxable")],
        targets=[("us_equity", 0.6, 0.05), ("bonds", 0.4, 0.05)],
        positions=[("tax", "VTI", 60.0, 100.0), ("tax", "BND", 40.0, 100.0)],
        prices={"VTI": 100.0, "BND": 100.0},
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    assert plan.trades == []
    assert plan.asset_classes_corrected == []


def test_plan_aggregates_buy_and_sell_totals() -> None:
    planner = _build_planner(
        accounts=[("roth", "Roth"), ("tax", "Taxable")],
        targets=[("us_equity", 0.5, 0.05), ("bonds", 0.5, 0.05)],
        positions=[("tax", "BND", 100.0, 100.0)],  # 100% bonds → buy us_equity
        prices={"BND": 100.0},
    )
    plan = planner.propose_trades("household", "hh1", snapshot_date=date(2026, 5, 9))
    # Bonds is overweight (sell) AND us_equity is underweight (buy);
    # both trades land at $5000 each on a $10k portfolio with 50/50 targets.
    assert plan.total_buy_value == 5000.0
    assert plan.total_sell_value == 5000.0
    assert sorted(plan.asset_classes_corrected) == ["bonds", "us_equity"]


_ = PriceData
_ = pytest

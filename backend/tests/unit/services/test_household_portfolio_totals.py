"""Tests for effective household portfolio totals."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.portfolio.totals import PortfolioTotals
from app.services.household_portfolio_totals import get_effective_portfolio_totals


def test_get_effective_portfolio_totals_prefers_household_invested_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.household_portfolio_totals.get_live_portfolio_totals",
        lambda *_args, **_kwargs: PortfolioTotals(
            cash_balance_total=75_000.0,
            invested_total_value=850_000.0,
        ),
    )
    household_service = SimpleNamespace(
        get_dashboard=lambda: SimpleNamespace(
            overview=SimpleNamespace(
                total_tracked_assets=1_382_265.3,
                invested_assets=1_342_864.71,
                cash_reserve=39_400.59,
            ),
            accounts=[
                SimpleNamespace(current_value=507_248.61, asset_group="taxable"),
                SimpleNamespace(current_value=347_053.83, asset_group="retirement"),
                SimpleNamespace(current_value=48_014.15, asset_group="retirement"),
                SimpleNamespace(current_value=8_428.38, asset_group="retirement"),
                SimpleNamespace(current_value=3_087.29, asset_group="education"),
                SimpleNamespace(current_value=39_400.59, asset_group="cash"),
            ],
            account_control=SimpleNamespace(
                status="review",
                summary="Review-only aliases do not affect totals.",
                blocking_issue_count=0,
            ),
        )
    )

    totals = get_effective_portfolio_totals(
        object(), household_service=household_service
    )

    assert totals.live_cash_inclusive_total_value == pytest.approx(925_000.0)
    assert totals.household_total_value == pytest.approx(1_382_265.3)
    assert totals.household_invested_total_value == pytest.approx(1_342_864.71)
    assert totals.household_cash_reserve == pytest.approx(39_400.59)
    assert totals.household_investment_accounts_count == 5
    assert totals.household_totals_trusted is True
    assert totals.account_control_status == "review"
    assert totals.effective_total_value == pytest.approx(1_382_265.3)
    assert totals.effective_invested_total_value == pytest.approx(1_342_864.71)


def test_get_effective_portfolio_totals_does_not_promote_blocked_household_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.household_portfolio_totals.get_live_portfolio_totals",
        lambda *_args, **_kwargs: PortfolioTotals(
            cash_balance_total=25_000.0,
            invested_total_value=500_000.0,
        ),
    )
    dashboard = SimpleNamespace(
        overview=SimpleNamespace(
            total_tracked_assets=1_500_000.0,
            invested_assets=1_450_000.0,
            cash_reserve=50_000.0,
        ),
        accounts=[],
        account_control=SimpleNamespace(
            status="blocked",
            summary="A material source account is not linked.",
            blocking_issue_count=1,
        ),
    )

    totals = get_effective_portfolio_totals(object(), dashboard=dashboard)

    assert totals.household_total_value == pytest.approx(1_500_000.0)
    assert totals.household_totals_trusted is False
    assert totals.account_control_blocking_issue_count == 1
    assert totals.effective_total_value == pytest.approx(525_000.0)
    assert totals.effective_invested_total_value == pytest.approx(500_000.0)


def test_get_effective_portfolio_totals_falls_back_to_live_totals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.household_portfolio_totals.get_live_portfolio_totals",
        lambda *_args, **_kwargs: PortfolioTotals(
            cash_balance_total=2_500.0,
            invested_total_value=18_000.0,
        ),
    )

    totals = get_effective_portfolio_totals(
        object(),
        household_service=SimpleNamespace(
            get_dashboard=lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        ),
    )

    assert totals.household_total_value is None
    assert totals.household_invested_total_value is None
    assert totals.household_investment_accounts_count == 0
    assert totals.household_totals_trusted is False
    assert totals.effective_total_value == pytest.approx(20_500.0)
    assert totals.effective_invested_total_value == pytest.approx(18_000.0)

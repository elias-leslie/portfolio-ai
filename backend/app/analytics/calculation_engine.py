"""Shared user-facing calculation helpers.

This module is the single source of truth for trade setup sizing, targets,
and portfolio-return-derived Sharpe calculations shown to the user.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.analytics.trade_calculations import calculate_stop_loss
from app.rules import get_rules

if TYPE_CHECKING:
    from app.storage import PortfolioStorage


@dataclass(frozen=True)
class TradeSetup:
    """Actionable trade setup derived from validated risk inputs."""

    stop_loss: float
    target_price: float
    risk_per_share: float
    reward_per_share: float
    risk_reward_ratio: float
    sample_share_count: int
    sample_dollar_size: float


def calculate_atr_stop_loss(
    storage: PortfolioStorage,
    symbol: str,
    entry_price: float,
) -> float | None:
    """Return the ATR-backed stop loss, or None when ATR is unavailable."""
    return calculate_stop_loss(storage, symbol, entry_price)


def calculate_expected_return_target(
    entry_price: float,
    expected_return_pct: float | None,
) -> float | None:
    """Convert a positive expected return percentage into a price target."""
    if expected_return_pct is None or expected_return_pct <= 0:
        return None
    return round(entry_price * (1 + (expected_return_pct / 100.0)), 2)


def calculate_position_size_from_risk(
    entry_price: float,
    stop_loss: float,
    risk_budget: float,
) -> int | None:
    """Calculate share count from dollar risk budget and stop distance."""
    if risk_budget <= 0 or stop_loss is None or entry_price <= stop_loss:
        return None
    risk_per_share = entry_price - stop_loss
    return int(risk_budget / risk_per_share)


def calculate_risk_reward_ratio(
    entry_price: float,
    stop_loss: float,
    target_price: float,
) -> float | None:
    """Return reward divided by risk when both are positive."""
    risk_per_share = entry_price - stop_loss
    reward_per_share = target_price - entry_price
    if risk_per_share <= 0 or reward_per_share <= 0:
        return None
    return round(reward_per_share / risk_per_share, 2)


def build_trade_setup(
    storage: PortfolioStorage,
    symbol: str,
    entry_price: float,
    expected_return_pct: float | None,
    risk_budget: float,
    portfolio_value: float,
    *,
    current_price: float | None = None,
    position_cap_pct: float | None = None,
) -> TradeSetup | None:
    """Build a complete trade setup from ATR stop, target, and sizing rules."""
    current_price = current_price or entry_price
    stop_loss = calculate_atr_stop_loss(storage, symbol, current_price)
    target_price = calculate_expected_return_target(entry_price, expected_return_pct)
    if stop_loss is None or target_price is None:
        return None

    risk_per_share = round(current_price - stop_loss, 2)
    reward_per_share = round(target_price - current_price, 2)
    risk_reward_ratio = calculate_risk_reward_ratio(current_price, stop_loss, target_price)
    if risk_per_share <= 0 or reward_per_share <= 0 or risk_reward_ratio is None:
        return None

    risk_based_shares = calculate_position_size_from_risk(current_price, stop_loss, risk_budget)
    if risk_based_shares is None or risk_based_shares <= 0:
        return None

    rules = get_rules()
    cap_pct = (
        position_cap_pct
        if position_cap_pct is not None
        else rules.paper_trading.default_position_pct
    )
    position_cap_dollars = portfolio_value * cap_pct
    cap_based_shares = int(position_cap_dollars / current_price) if current_price > 0 else 0
    sample_share_count = min(risk_based_shares, cap_based_shares) if cap_based_shares > 0 else 0
    if sample_share_count <= 0:
        return None

    sample_dollar_size = round(sample_share_count * current_price, 2)
    if sample_dollar_size < rules.position_sizing.min_position_value:
        return None

    return TradeSetup(
        stop_loss=round(stop_loss, 2),
        target_price=target_price,
        risk_per_share=risk_per_share,
        reward_per_share=reward_per_share,
        risk_reward_ratio=risk_reward_ratio,
        sample_share_count=sample_share_count,
        sample_dollar_size=sample_dollar_size,
    )


def calculate_portfolio_sharpe(
    storage: PortfolioStorage,
    account_ids: list[str],
    risk_free_rate: float = 0.045,
) -> float | None:
    """Calculate Sharpe ratio from stored daily portfolio equity history."""
    daily_returns = _get_portfolio_daily_returns(storage, account_ids)
    if len(daily_returns) < 2:
        return None

    mean_return = sum(daily_returns) / len(daily_returns)
    variance = sum((daily_return - mean_return) ** 2 for daily_return in daily_returns) / len(
        daily_returns
    )
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return None

    daily_risk_free_rate = risk_free_rate / 252
    excess_return = mean_return - daily_risk_free_rate
    sharpe_ratio = excess_return * math.sqrt(252) / std_dev
    if math.isnan(sharpe_ratio) or math.isinf(sharpe_ratio):
        return None
    return sharpe_ratio


def _get_portfolio_daily_returns(
    storage: PortfolioStorage,
    account_ids: list[str],
) -> list[float]:
    """Build an aggregate daily return series from account-level equity snapshots."""
    from app.portfolio.drawdown_db import get_drawdown_history  # noqa: PLC0415

    if not account_ids:
        return []

    equity_by_date: dict[str, float] = defaultdict(float)
    for account_id in account_ids:
        for snapshot in get_drawdown_history(storage, account_id, days=365):
            snapshot_date = str(snapshot["date"])
            equity_by_date[snapshot_date] += float(snapshot["equity"])

    if len(equity_by_date) < 2:
        return []

    ordered_dates = sorted(equity_by_date)
    daily_returns: list[float] = []
    previous_equity: float | None = None
    for snapshot_date in ordered_dates:
        current_equity = equity_by_date[snapshot_date]
        if previous_equity is not None and previous_equity > 0:
            daily_returns.append((current_equity - previous_equity) / previous_equity)
        previous_equity = current_equity

    return daily_returns

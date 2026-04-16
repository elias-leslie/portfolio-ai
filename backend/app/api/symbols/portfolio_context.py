"""Canonical live portfolio context for symbol-level decisions."""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.portfolio.fund_lookthrough import get_fund_lookthroughs
from app.services.household_portfolio_totals import get_effective_portfolio_totals
from app.storage.facade import PortfolioStorage
from app.storage.helpers import row_to_dict, rows_to_dicts

logger = get_logger(__name__)


def _empty_context() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    return {}, {"total_value": 0.0, "num_holdings": 0}


def _enrich_position_concentration(
    storage: PortfolioStorage,
    positions_by_symbol: dict[str, dict[str, Any]],
    total_value: float,
) -> None:
    if not positions_by_symbol:
        return

    fund_profiles = get_fund_lookthroughs(list(positions_by_symbol), storage)
    for symbol, position in positions_by_symbol.items():
        try:
            shares = float(position.get("shares") or 0.0)
            current_price = float(position.get("current_price") or 0.0)
        except (TypeError, ValueError):
            continue

        current_value = abs(shares * current_price)
        if current_value <= 0 or total_value <= 0:
            continue

        weight_pct = (current_value / total_value) * 100
        position["weight_pct"] = weight_pct
        position["concentration_weight_pct"] = weight_pct
        position["concentration_method"] = "line_item"
        position["top_exposure_name"] = symbol

        profile = fund_profiles.get(symbol)
        if profile is None or not profile.top_holdings:
            continue

        top_holding = max(profile.top_holdings, key=lambda holding: holding.weight, default=None)
        if top_holding is None or top_holding.weight <= 0:
            continue

        position["concentration_method"] = "lookthrough"
        position["concentration_weight_pct"] = weight_pct * top_holding.weight
        position["top_exposure_name"] = top_holding.name or top_holding.symbol


def fetch_symbol_portfolio_context(
    storage: PortfolioStorage,
    symbols: list[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return aggregate real-account position context keyed by symbol.

    A symbol can be held across multiple accounts. Symbol-level decisions,
    workflow state, and watchlist rows need the aggregate live position rather
    than whichever row the database returns first.
    """
    unique_symbols = sorted({symbol.upper() for symbol in symbols if symbol})
    if not unique_symbols:
        return _empty_context()

    placeholders = ", ".join(["%s"] * len(unique_symbols))
    positions_by_symbol: dict[str, dict[str, Any]] = {}
    num_holdings = 0

    try:
        with storage.connection() as conn:
            position_result = conn.execute(
                f"""
                SELECT
                    UPPER(p.symbol) AS symbol,
                    SUM(p.shares) AS shares,
                    SUM(p.shares * p.cost_basis) / NULLIF(SUM(p.shares), 0) AS cost_basis,
                    MAX(pc.price) AS current_price
                FROM portfolio_positions p
                JOIN portfolio_accounts a ON a.id = p.account_id
                LEFT JOIN price_cache pc ON UPPER(p.symbol) = UPPER(pc.symbol)
                WHERE UPPER(p.symbol) IN ({placeholders})
                  AND a.account_type != 'paper'
                  AND p.position_type != 'paper'
                GROUP BY UPPER(p.symbol)
                """,
                unique_symbols,
            )
            position_rows = position_result.fetchall()
            if position_rows and position_result.description:
                positions_by_symbol = {
                    str(row["symbol"]): row
                    for row in rows_to_dicts(position_rows, position_result.description)
                    if float(row.get("shares") or 0.0) > 0
                }

            holdings_result = conn.execute(
                """
                SELECT COUNT(DISTINCT UPPER(p.symbol)) AS num_holdings
                FROM portfolio_positions p
                JOIN portfolio_accounts a ON a.id = p.account_id
                WHERE a.account_type != 'paper'
                  AND p.position_type != 'paper'
                """
            )
            holdings_row = holdings_result.fetchone()
            if holdings_row and holdings_result.description:
                holdings = row_to_dict(holdings_row, holdings_result.description)
                num_holdings = int(holdings.get("num_holdings") or 0)
    except Exception as exc:
        logger.warning("symbol_portfolio_context_failed", error=str(exc))
        return _empty_context()

    try:
        totals = get_effective_portfolio_totals(
            storage,
            include_paper=False,
        )
        total_value = totals.effective_invested_total_value
    except Exception as exc:
        logger.warning("symbol_portfolio_total_failed", error=str(exc))
        total_value = 0.0

    _enrich_position_concentration(storage, positions_by_symbol, total_value)

    return positions_by_symbol, {
        "total_value": total_value,
        "num_holdings": num_holdings,
    }

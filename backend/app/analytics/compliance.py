"""Compliance and tax-related analytics (GAP-053).

GAP-053: Wash Sale Detection
Detects wash sales for tax reporting purposes.

A wash sale occurs when you:
1. Sell a security at a loss
2. Buy substantially identical security within 30 days before or after

The loss is disallowed for tax purposes and added to cost basis of new shares.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from typing import Any

    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Wash sale window: 30 days before and after sale
WASH_SALE_WINDOW_DAYS = 30


@dataclass
class WashSaleViolation:
    """A detected wash sale violation."""

    symbol: str
    sell_date: date
    sell_quantity: float
    sell_price: float
    loss_amount: float  # The disallowed loss
    triggering_buy_date: date
    triggering_buy_quantity: float
    triggering_buy_price: float
    disallowed_loss: float  # Loss that cannot be claimed
    adjusted_basis: float  # New cost basis for bought shares


@dataclass
class WashSaleReport:
    """Summary of wash sale analysis."""

    symbol: str | None  # None if portfolio-wide
    violations: list[WashSaleViolation]
    total_disallowed_loss: float
    periods_analyzed: int
    start_date: date
    end_date: date


@dataclass
class Trade:
    """Represents a single trade."""

    symbol: str
    date: date
    action: str  # "BUY" or "SELL"
    quantity: float
    price: float
    cost_basis: float | None = None  # For sells


def detect_wash_sales_for_symbol(
    trades: list[Trade],
    window_days: int = WASH_SALE_WINDOW_DAYS,
) -> list[WashSaleViolation]:
    """Detect wash sales in a list of trades for a single symbol.

    Args:
        trades: List of trades for one symbol, sorted by date
        window_days: Days before/after sale to check (default 30)

    Returns:
        List of WashSaleViolation objects
    """
    violations: list[WashSaleViolation] = []

    # Sort trades by date
    sorted_trades = sorted(trades, key=lambda t: t.date)

    for i, trade in enumerate(sorted_trades):
        # Only check sells
        if trade.action != "SELL":
            continue

        # Calculate if this is a loss sale
        if trade.cost_basis is None:
            # Can't determine if loss without cost basis
            continue

        proceeds = trade.quantity * trade.price
        cost = trade.cost_basis
        gain_loss = proceeds - cost

        if gain_loss >= 0:
            # Not a loss, no wash sale possible
            continue

        loss_amount = abs(gain_loss)
        sell_date = trade.date

        # Check for buys within window
        window_start = sell_date - timedelta(days=window_days)
        window_end = sell_date + timedelta(days=window_days)

        for j, other_trade in enumerate(sorted_trades):
            if i == j:
                continue
            if other_trade.action != "BUY":
                continue
            if not (window_start <= other_trade.date <= window_end):
                continue

            # Found a wash sale!
            # Calculate disallowed loss (proportional to shares)
            wash_quantity = min(trade.quantity, other_trade.quantity)
            disallowed_pct = wash_quantity / trade.quantity
            disallowed_loss = loss_amount * disallowed_pct

            # New basis = buy price + disallowed loss per share
            adjusted_basis = other_trade.price + (disallowed_loss / wash_quantity)

            violations.append(
                WashSaleViolation(
                    symbol=trade.symbol,
                    sell_date=sell_date,
                    sell_quantity=trade.quantity,
                    sell_price=trade.price,
                    loss_amount=loss_amount,
                    triggering_buy_date=other_trade.date,
                    triggering_buy_quantity=other_trade.quantity,
                    triggering_buy_price=other_trade.price,
                    disallowed_loss=disallowed_loss,
                    adjusted_basis=adjusted_basis,
                )
            )

            logger.info(
                "wash_sale_detected",
                symbol=trade.symbol,
                sell_date=str(sell_date),
                buy_date=str(other_trade.date),
                disallowed_loss=f"${disallowed_loss:.2f}",
            )

            # Only count first matching buy (to avoid double-counting)
            break

    return violations


def get_trades_from_database(
    storage: PortfolioStorage,
    symbol: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[Trade]:
    """Fetch trades from database.

    Args:
        storage: Database storage instance
        symbol: Optional filter by symbol
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of Trade objects
    """
    query = """
        SELECT symbol, created_at::date as trade_date, action, quantity, price
        FROM paper_trades
        WHERE 1=1
    """
    params: list[str | int | float | bool | None] = []

    if symbol:
        query += " AND symbol = %s"
        params.append(symbol)

    if start_date:
        query += " AND created_at >= %s"
        params.append(str(start_date))

    if end_date:
        query += " AND created_at <= %s"
        params.append(str(end_date))

    query += " ORDER BY symbol, created_at"

    result = storage.query(query, params)  # type: ignore[arg-type]

    trades: list[Trade] = []
    for row in result.iter_rows(named=True):
        action = str(row["action"]).upper()
        if action not in ("BUY", "SELL"):
            continue

        trades.append(
            Trade(
                symbol=row["symbol"],
                date=row["trade_date"],
                action=action,
                quantity=float(row["quantity"]),
                price=float(row["price"]),
            )
        )

    return trades


def calculate_cost_basis(trades: list[Trade]) -> list[Trade]:
    """Calculate cost basis for sell trades using FIFO.

    Args:
        trades: List of trades (sorted by date)

    Returns:
        Same trades with cost_basis populated for sells
    """
    # Group by symbol
    by_symbol: dict[str, list[Trade]] = {}
    for trade in trades:
        if trade.symbol not in by_symbol:
            by_symbol[trade.symbol] = []
        by_symbol[trade.symbol].append(trade)

    result: list[Trade] = []

    for _symbol, symbol_trades in by_symbol.items():
        # Track lots for FIFO
        lots: list[tuple[float, float]] = []  # (quantity, price)

        for trade in sorted(symbol_trades, key=lambda t: t.date):
            if trade.action == "BUY":
                lots.append((trade.quantity, trade.price))
                result.append(trade)
            else:  # SELL
                # Calculate cost basis using FIFO
                remaining = trade.quantity
                total_cost = 0.0

                while remaining > 0 and lots:
                    lot_qty, lot_price = lots[0]
                    if lot_qty <= remaining:
                        # Use entire lot
                        total_cost += lot_qty * lot_price
                        remaining -= lot_qty
                        lots.pop(0)
                    else:
                        # Use partial lot
                        total_cost += remaining * lot_price
                        lots[0] = (lot_qty - remaining, lot_price)
                        remaining = 0

                trade.cost_basis = total_cost
                result.append(trade)

    return result


def check_wash_sales(
    storage: PortfolioStorage,
    symbol: str | None = None,
    tax_year: int | None = None,
) -> WashSaleReport:
    """Check for wash sales in paper trades.

    Args:
        storage: Database storage instance
        symbol: Optional symbol filter
        tax_year: Year to analyze (default: current year)

    Returns:
        WashSaleReport with detected violations
    """
    if tax_year is None:
        tax_year = date.today().year

    start_date = date(tax_year, 1, 1)
    end_date = date(tax_year, 12, 31)

    # Extend range to catch wash sales spanning year boundary
    query_start = start_date - timedelta(days=WASH_SALE_WINDOW_DAYS)
    query_end = end_date + timedelta(days=WASH_SALE_WINDOW_DAYS)

    # Fetch trades
    trades = get_trades_from_database(storage, symbol, query_start, query_end)

    if not trades:
        return WashSaleReport(
            symbol=symbol,
            violations=[],
            total_disallowed_loss=0.0,
            periods_analyzed=0,
            start_date=start_date,
            end_date=end_date,
        )

    # Calculate cost basis
    trades_with_basis = calculate_cost_basis(trades)

    # Group by symbol for detection
    by_symbol: dict[str, list[Trade]] = {}
    for trade in trades_with_basis:
        if trade.symbol not in by_symbol:
            by_symbol[trade.symbol] = []
        by_symbol[trade.symbol].append(trade)

    # Detect wash sales
    all_violations: list[WashSaleViolation] = []
    for _sym, sym_trades in by_symbol.items():
        violations = detect_wash_sales_for_symbol(sym_trades)
        # Only include violations where sell was in tax year
        for v in violations:
            if start_date <= v.sell_date <= end_date:
                all_violations.append(v)

    total_disallowed = sum(v.disallowed_loss for v in all_violations)

    logger.info(
        "wash_sale_check_complete",
        symbol=symbol or "ALL",
        tax_year=tax_year,
        violations=len(all_violations),
        total_disallowed=f"${total_disallowed:.2f}",
    )

    return WashSaleReport(
        symbol=symbol,
        violations=all_violations,
        total_disallowed_loss=total_disallowed,
        periods_analyzed=len(trades),
        start_date=start_date,
        end_date=end_date,
    )


def get_wash_sale_summary(
    storage: PortfolioStorage,
    tax_year: int | None = None,
) -> dict[str, Any]:
    """Get summary of wash sales for tax reporting.

    Args:
        storage: Database storage instance
        tax_year: Year to analyze

    Returns:
        Summary dict suitable for UI display
    """
    report = check_wash_sales(storage, tax_year=tax_year)

    # Group violations by symbol
    by_symbol: dict[str, float] = {}
    for v in report.violations:
        if v.symbol not in by_symbol:
            by_symbol[v.symbol] = 0.0
        by_symbol[v.symbol] += v.disallowed_loss

    return {
        "tax_year": report.start_date.year,
        "total_violations": len(report.violations),
        "total_disallowed_loss": report.total_disallowed_loss,
        "symbols_affected": list(by_symbol.keys()),
        "by_symbol": by_symbol,
        "violations": [
            {
                "symbol": v.symbol,
                "sell_date": str(v.sell_date),
                "buy_date": str(v.triggering_buy_date),
                "disallowed_loss": v.disallowed_loss,
                "adjusted_basis": v.adjusted_basis,
            }
            for v in report.violations
        ],
    }

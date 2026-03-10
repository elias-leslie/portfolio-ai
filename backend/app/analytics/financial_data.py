"""Database services for financial data extraction (short interest, cash flow, ownership)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.storage.connection import get_connection_manager


@dataclass
class ShortInterestData:
    """Short interest data from database."""

    symbol: str
    as_of_date: str
    short_shares: float | None
    short_ratio: float | None
    short_percent_of_float: float | None
    short_percent_of_outstanding: float | None
    short_prior_month: float | None
    pct_change: float | None
    source: str


@dataclass
class CashFlowData:
    """Cash flow metrics data from database."""

    symbol: str
    as_of_date: str
    operating_cash_flow: float | None
    free_cash_flow: float | None
    capital_expenditure: float | None
    fcf_yield: float | None
    cash_flow_margin: float | None
    fcf_per_share: float | None
    cash_conversion_ratio: float | None
    source: str


@dataclass
class InsiderTransaction:
    """Insider transaction data from database."""

    symbol: str
    insider_name: str | None
    insider_title: str | None
    transaction_type: str | None
    transaction_date: str | None
    shares: float | None
    value: float | None
    shares_owned_after: float | None


@dataclass
class InstitutionalHolding:
    """Institutional holding data from database."""

    symbol: str
    holder_name: str | None
    shares: float | None
    value: float | None
    pct_held: float | None
    pct_change: float | None
    report_date: str | None


@dataclass
class InstitutionalSummary:
    """Institutional ownership summary from database."""

    symbol: str
    as_of_date: str | None
    total_institutions: int | None
    total_shares_held: float | None
    pct_held_institutions: float | None
    pct_held_insiders: float | None
    institutions_increased: int | None
    institutions_decreased: int | None
    top_holders: list[InstitutionalHolding]


def safe_float(val: str | int | float | bool | None) -> float | None:
    """Convert DatabaseValue to float, handling NaN for JSON serialization."""
    if val is None or isinstance(val, bool):
        return None
    try:
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            return None
        return f_val
    except (ValueError, TypeError):
        return None


def safe_int(val: str | int | float | bool | None) -> int | None:
    """Convert DatabaseValue to int."""
    if val is None or isinstance(val, bool):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def safe_str(val: str | int | float | bool | None) -> str | None:
    """Convert DatabaseValue to str."""
    if val is None or isinstance(val, bool):
        return None
    return str(val)


def safe_date_str(val: object) -> str | None:
    """Convert DatabaseValue date to ISO string."""
    isoformat = getattr(val, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return None


def get_short_interest(symbol: str) -> ShortInterestData | None:
    """Get most recent short interest data for a symbol.

    Args:
        symbol: Stock symbol (e.g., "AAPL")

    Returns:
        ShortInterestData or None if no data found
    """
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, as_of_date, short_shares, short_ratio,
                   short_percent_of_float, short_percent_of_outstanding,
                   short_prior_month, short_pct_change, source
            FROM short_interest
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        )
        row = result.fetchone()

    if row is None:
        return None

    return ShortInterestData(
        symbol=safe_str(row[0]) or "",
        as_of_date=safe_date_str(row[1]) or "",
        short_shares=safe_float(row[2]),
        short_ratio=safe_float(row[3]),
        short_percent_of_float=safe_float(row[4]),
        short_percent_of_outstanding=safe_float(row[5]),
        short_prior_month=safe_float(row[6]),
        pct_change=safe_float(row[7]),
        source=safe_str(row[8]) or "yfinance",
    )


def get_cash_flow_metrics(symbol: str) -> CashFlowData | None:
    """Get most recent cash flow metrics for a symbol.

    Args:
        symbol: Stock symbol (e.g., "AAPL")

    Returns:
        CashFlowData or None if no data found
    """
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, as_of_date, operating_cash_flow, free_cash_flow,
                   capital_expenditure, fcf_yield, cash_flow_margin,
                   fcf_per_share, cash_conversion_ratio, source
            FROM cash_flow_metrics
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        )
        row = result.fetchone()

    if row is None:
        return None

    return CashFlowData(
        symbol=safe_str(row[0]) or "",
        as_of_date=safe_date_str(row[1]) or "",
        operating_cash_flow=safe_float(row[2]),
        free_cash_flow=safe_float(row[3]),
        capital_expenditure=safe_float(row[4]),
        fcf_yield=safe_float(row[5]),
        cash_flow_margin=safe_float(row[6]),
        fcf_per_share=safe_float(row[7]),
        cash_conversion_ratio=safe_float(row[8]),
        source=safe_str(row[9]) or "yfinance",
    )


def get_insider_transactions(symbol: str, limit: int = 20) -> list[InsiderTransaction]:
    """Get recent insider transactions for a symbol.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        limit: Maximum number of transactions to return

    Returns:
        List of insider transactions
    """
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, insider_name, insider_title, transaction_type,
                   transaction_date, shares, value, shares_owned_after
            FROM insider_transactions
            WHERE symbol = %s
            ORDER BY transaction_date DESC
            LIMIT %s
            """,
            (symbol.upper(), limit),
        )
        rows = result.fetchall()

    transactions = []
    for row in rows:
        transactions.append(
            InsiderTransaction(
                symbol=safe_str(row[0]) or "",
                insider_name=safe_str(row[1]),
                insider_title=safe_str(row[2]),
                transaction_type=safe_str(row[3]),
                transaction_date=safe_date_str(row[4]),
                shares=safe_float(row[5]),
                value=safe_float(row[6]),
                shares_owned_after=safe_float(row[7]),
            )
        )

    return transactions


def get_institutional_holdings(symbol: str, top_n: int = 10) -> InstitutionalSummary | None:
    """Get institutional ownership summary and top holders.

    Args:
        symbol: Stock symbol (e.g., "AAPL")
        top_n: Number of top holders to include

    Returns:
        InstitutionalSummary or None if no data found
    """
    mgr = get_connection_manager()

    # Get summary data
    with mgr.connection() as conn:
        summary_result = conn.execute(
            """
            SELECT symbol, as_of_date, total_institutions, total_shares_held,
                   pct_held_institutions, pct_held_insiders,
                   institutions_increased, institutions_decreased
            FROM institutional_ownership_summary
            WHERE symbol = %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        )
        summary_row = summary_result.fetchone()

        # Get top holders
        holders_result = conn.execute(
            """
            SELECT symbol, holder_name, shares, value, pct_held, pct_change, report_date
            FROM institutional_holdings
            WHERE symbol = %s
            ORDER BY value DESC NULLS LAST
            LIMIT %s
            """,
            (symbol.upper(), top_n),
        )
        holder_rows = holders_result.fetchall()

    # Parse top holders
    top_holders = []
    for row in holder_rows:
        top_holders.append(
            InstitutionalHolding(
                symbol=safe_str(row[0]) or "",
                holder_name=safe_str(row[1]),
                shares=safe_float(row[2]),
                value=safe_float(row[3]),
                pct_held=safe_float(row[4]),
                pct_change=safe_float(row[5]),
                report_date=safe_date_str(row[6]),
            )
        )

    if summary_row is None and not top_holders:
        return None

    return InstitutionalSummary(
        symbol=symbol.upper(),
        as_of_date=safe_date_str(summary_row[1]) if summary_row else None,
        total_institutions=safe_int(summary_row[2]) if summary_row else None,
        total_shares_held=safe_float(summary_row[3]) if summary_row else None,
        pct_held_institutions=safe_float(summary_row[4]) if summary_row else None,
        pct_held_insiders=safe_float(summary_row[5]) if summary_row else None,
        institutions_increased=safe_int(summary_row[6]) if summary_row else None,
        institutions_decreased=safe_int(summary_row[7]) if summary_row else None,
        top_holders=top_holders,
    )

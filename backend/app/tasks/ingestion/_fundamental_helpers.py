"""Private helper functions for equity fundamental data ingestion.

This module contains internal helpers used by fundamental_ingestion.py.
Not part of the public API — import from fundamental_ingestion instead.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np

from app.storage import PortfolioStorage


def to_python(value: Any) -> Any:
    """Convert numpy types to native Python types for database insertion."""
    if value is None:
        return None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if np.isnan(value) else float(value)
    if isinstance(value, (np.bool_, np.ndarray)):
        return bool(value) if isinstance(value, np.bool_) else value.tolist()
    return value


def ensure_symbol_exists(storage: PortfolioStorage, symbol: str) -> None:
    """Ensure symbol exists in symbols table (FK constraint)."""
    storage.execute(
        """
        INSERT INTO symbols (symbol, security_type, created_at)
        VALUES ($1, 'equity', NOW())
        ON CONFLICT (symbol) DO NOTHING
        """,
        [symbol],
    )


def _coerce_date(value: Any) -> datetime | None:
    """Coerce various date/datetime types to datetime."""
    if value is None:
        return None
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if hasattr(value, "date"):
        return datetime.combine(value.date(), datetime.min.time())
    return None


def insert_cash_flow(storage: PortfolioStorage, data: dict[str, Any], as_of_date: date) -> None:
    """Insert cash flow metrics."""
    ensure_symbol_exists(storage, data["symbol"])
    query = """
        INSERT INTO cash_flow_metrics (
            symbol, as_of_date, operating_cash_flow, free_cash_flow,
            capital_expenditure, fcf_yield, cash_flow_margin,
            fcf_per_share, cash_conversion_ratio, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'yfinance', NOW())
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            operating_cash_flow = EXCLUDED.operating_cash_flow,
            free_cash_flow = EXCLUDED.free_cash_flow,
            capital_expenditure = EXCLUDED.capital_expenditure,
            fcf_yield = EXCLUDED.fcf_yield,
            cash_flow_margin = EXCLUDED.cash_flow_margin,
            fcf_per_share = EXCLUDED.fcf_per_share,
            cash_conversion_ratio = EXCLUDED.cash_conversion_ratio,
            updated_at = NOW()
    """
    storage.execute(
        query,
        [
            data["symbol"],
            datetime.combine(as_of_date, datetime.min.time()),
            to_python(data.get("operating_cash_flow")),
            to_python(data.get("free_cash_flow")),
            to_python(data.get("capital_expenditure")),
            to_python(data.get("fcf_yield")),
            to_python(data.get("cash_flow_margin")),
            to_python(data.get("fcf_per_share")),
            to_python(data.get("cash_conversion_ratio")),
        ],
    )


def insert_insider_transaction(storage: PortfolioStorage, data: dict[str, Any]) -> None:
    """Insert insider transaction."""
    ensure_symbol_exists(storage, data["symbol"])
    query = """
        INSERT INTO insider_transactions (
            symbol, insider_name, insider_title, transaction_type,
            transaction_date, shares, value, shares_owned_after, source
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'yfinance')
        ON CONFLICT (symbol, insider_name, transaction_date, transaction_type, shares)
        DO NOTHING
    """
    storage.execute(
        query,
        [
            data["symbol"],
            data.get("insider_name"),
            data.get("insider_title"),
            data.get("transaction_type"),
            _coerce_date(data.get("transaction_date")),
            to_python(data.get("shares")),
            to_python(data.get("value")),
            to_python(data.get("shares_owned_after")),
        ],
    )


def insert_institutional_holding(storage: PortfolioStorage, data: dict[str, Any]) -> None:
    """Insert institutional holding."""
    ensure_symbol_exists(storage, data["symbol"])
    query = """
        INSERT INTO institutional_holdings (
            symbol, holder_name, shares, value, pct_held, report_date, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, 'yfinance', NOW())
        ON CONFLICT (symbol, holder_name, report_date)
        DO UPDATE SET
            shares = EXCLUDED.shares,
            value = EXCLUDED.value,
            pct_held = EXCLUDED.pct_held,
            updated_at = NOW()
    """
    storage.execute(
        query,
        [
            data["symbol"],
            data.get("holder_name"),
            to_python(data.get("shares")),
            to_python(data.get("value")),
            to_python(data.get("pct_held")),
            _coerce_date(data.get("report_date")),
        ],
    )


def insert_institutional_summary(
    storage: PortfolioStorage, data: dict[str, Any], as_of_date: date
) -> None:
    """Insert institutional ownership summary."""
    ensure_symbol_exists(storage, data["symbol"])
    query = """
        INSERT INTO institutional_ownership_summary (
            symbol, as_of_date, total_institutions, pct_held_institutions,
            pct_held_insiders, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, 'yfinance', NOW())
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            total_institutions = EXCLUDED.total_institutions,
            pct_held_institutions = EXCLUDED.pct_held_institutions,
            pct_held_insiders = EXCLUDED.pct_held_insiders,
            updated_at = NOW()
    """
    storage.execute(
        query,
        [
            data["symbol"],
            datetime.combine(as_of_date, datetime.min.time()),
            to_python(data.get("total_institutions")),
            to_python(data.get("pct_held_institutions")),
            to_python(data.get("pct_held_insiders")),
        ],
    )


def insert_short_interest(
    storage: PortfolioStorage, data: dict[str, Any], as_of_date: date
) -> None:
    """Insert short interest data and dual-write to summary table."""
    ensure_symbol_exists(storage, data["symbol"])
    as_of_datetime = datetime.combine(as_of_date, datetime.min.time())

    storage.execute(
        """
        INSERT INTO short_interest (
            symbol, as_of_date, short_shares, short_ratio,
            short_percent_of_float, short_percent_of_outstanding,
            short_prior_month, source, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'yfinance', NOW())
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            short_shares = EXCLUDED.short_shares,
            short_ratio = EXCLUDED.short_ratio,
            short_percent_of_float = EXCLUDED.short_percent_of_float,
            short_percent_of_outstanding = EXCLUDED.short_percent_of_outstanding,
            short_prior_month = EXCLUDED.short_prior_month,
            updated_at = NOW()
        """,
        [
            data["symbol"],
            as_of_datetime,
            to_python(data.get("short_shares")),
            to_python(data.get("short_ratio")),
            to_python(data.get("short_percent_of_float")),
            to_python(data.get("short_percent_of_outstanding")),
            to_python(data.get("short_prior_month")),
        ],
    )

    storage.execute(
        """
        INSERT INTO short_interest_summary (
            symbol, as_of_date, shares_short, short_ratio, short_percent_of_float
        ) VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (symbol, as_of_date)
        DO UPDATE SET
            shares_short = EXCLUDED.shares_short,
            short_ratio = EXCLUDED.short_ratio,
            short_percent_of_float = EXCLUDED.short_percent_of_float,
            updated_at = NOW()
        """,
        [
            data["symbol"],
            as_of_datetime,
            to_python(data.get("short_shares")),
            to_python(data.get("short_ratio")),
            to_python(data.get("short_percent_of_float")),
        ],
    )

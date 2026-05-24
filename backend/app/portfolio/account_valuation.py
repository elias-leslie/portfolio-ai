"""Shared live account valuation helpers for portfolio-linked accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.portfolio.current_facts import calculate_current_position_fact
from app.portfolio.models import PriceData
from app.utils.market_hours import get_market_status


@dataclass(slots=True)
class AccountValuation:
    account_id: str
    priced_positions_value: float
    effective_cash_balance: float
    total_value: float
    priced_position_count: int
    quote_updated_at: datetime | None
    quote_freshness_status: str
    quote_freshness_label: str
    quote_source: str | None
    total_position_count: int = 0


def _normalize_quote_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _quote_freshness(quote_updated_at: datetime | None) -> tuple[str, str]:
    if quote_updated_at is None:
        return "not_applicable", "No live quotes"

    now = datetime.now(UTC)
    age = now - quote_updated_at
    market_status = get_market_status(now)
    if market_status == "open":
        fresh_threshold = timedelta(minutes=2)
        aging_threshold = timedelta(minutes=15)
        fresh_label = "Live quotes"
    else:
        fresh_threshold = timedelta(hours=4)
        aging_threshold = timedelta(hours=24)
        fresh_label = "Latest close"

    if age <= fresh_threshold:
        return "fresh", fresh_label
    if age <= aging_threshold:
        return "aging", "Refresh soon"
    return "stale", "Stale quotes"


def calculate_account_valuations(
    accounts: list[Any],
    positions: list[Any],
    price_data: dict[str, PriceData],
    *,
    cash_overrides: dict[str, float] | None = None,
) -> dict[str, AccountValuation]:
    """Return live per-account valuations using current prices plus best cash."""
    cash_overrides = cash_overrides or {}
    quote_times_by_account: dict[str, list[datetime]] = {}
    quote_sources_by_account: dict[str, set[str]] = {}
    values: dict[str, AccountValuation] = {}

    for account in accounts:
        account_id = str(account.id)
        effective_cash_balance = float(
            cash_overrides.get(
                account_id,
                float(getattr(account, "cash_balance", 0.0) or 0.0),
            )
        )
        values[account_id] = AccountValuation(
            account_id=account_id,
            priced_positions_value=0.0,
            effective_cash_balance=effective_cash_balance,
            total_value=effective_cash_balance,
            priced_position_count=0,
            quote_updated_at=None,
            quote_freshness_status="not_applicable",
            quote_freshness_label="No live quotes",
            quote_source=None,
        )

    for position in positions:
        account_id = str(position.account_id)
        valuation = values.get(account_id)
        if valuation is None:
            continue
        if float(getattr(position, "shares", 0.0) or 0.0) != 0.0:
            valuation.total_position_count += 1
        price = price_data.get(str(position.symbol))
        if price is None or price.error:
            continue
        current_fact = calculate_current_position_fact(
            symbol=str(position.symbol),
            shares=float(getattr(position, "shares", 0.0) or 0.0),
            cost_basis=float(getattr(position, "cost_basis", 0.0) or 0.0),
            position_type=str(getattr(position, "position_type", "long")),
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue
        valuation.priced_positions_value += float(current_fact.current_value)
        valuation.priced_position_count += 1
        normalized_quote_time = _normalize_quote_timestamp(price.cached_at)
        if normalized_quote_time is not None:
            quote_times_by_account.setdefault(account_id, []).append(normalized_quote_time)
        if price.source:
            quote_sources_by_account.setdefault(account_id, set()).add(str(price.source))

    for account_id, valuation in values.items():
        valuation.total_value = valuation.effective_cash_balance + valuation.priced_positions_value
        quote_times = quote_times_by_account.get(account_id) or []
        valuation.quote_updated_at = min(quote_times) if quote_times else None
        (
            valuation.quote_freshness_status,
            valuation.quote_freshness_label,
        ) = _quote_freshness(valuation.quote_updated_at)
        sources = sorted(quote_sources_by_account.get(account_id) or [])
        valuation.quote_source = None if not sources else sources[0] if len(sources) == 1 else "mixed"

    return values


def summarize_quote_freshness(
    account_valuations: dict[str, AccountValuation],
) -> tuple[datetime | None, str | None, str | None]:
    """Return portfolio-wide quote freshness from per-account valuations."""
    quote_times = [
        valuation.quote_updated_at
        for valuation in account_valuations.values()
        if valuation.quote_updated_at is not None
        and valuation.priced_position_count > 0
    ]
    if not quote_times:
        return None, None, None
    quote_updated_at = min(quote_times)
    status, label = _quote_freshness(quote_updated_at)
    return quote_updated_at, status, label

"""Flow-adjusted returns for a fixed, fully observed account universe."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from typing import Any

from app.utils.market_hours import is_trading_day

MIN_SHARPE_OBSERVATIONS = 60
RETURN_ACTIVITY_TYPES = frozenset(
    {
        "BUY",
        "SELL",
        "DIVIDEND",
        "SUBSTITUTE_DIVIDEND",
        "REI",
        "STOCK_DIVIDEND",
        "INTEREST",
        "FEE",
        "TAX",
        "OPTIONEXPIRATION",
        "OPTIONASSIGNMENT",
        "OPTIONEXERCISE",
        "SPLIT",
    }
)


@dataclass(frozen=True)
class FlowAdjustedSeries:
    dates: tuple[date, ...] = ()
    returns: tuple[float, ...] = ()
    reason: str | None = None


def aligned_returns(
    snapshots: dict[str, dict[date, float]],
    flows: dict[tuple[str, date], float],
    sessions: list[date],
) -> FlowAdjustedSeries:
    """Daily Modified Dietz; intraday flow times are unknown (midday weight)."""
    if not snapshots or not sessions:
        return FlowAdjustedSeries(reason="No dated valuations are available.")
    # Require every account at both endpoints; missing history never means zero.
    common = set.intersection(*(set(history) for history in snapshots.values()))
    common &= set(sessions)
    if len(common) < 2:
        return FlowAdjustedSeries(
            reason="The selected accounts do not have overlapping valuation history."
        )
    first, last = min(common), max(common)
    days = [d for d in sessions if first <= d <= last]
    if any(d not in common for d in days):
        return FlowAdjustedSeries(
            reason="Missing account valuations interrupt the common trading-day history."
        )
    returns = []
    for before, after in pairwise(days):
        start = sum(h[before] for h in snapshots.values())
        end = sum(h[after] for h in snapshots.values())
        flow = sum(
            amount
            for (account, day), amount in flows.items()
            if account in snapshots and before < day <= after
        )
        denominator = start + 0.5 * flow
        if denominator <= 0 or start < 0 or end < 0:
            return FlowAdjustedSeries(
                reason="A nonpositive capital base prevents a meaningful return."
            )
        value = (end - start - flow) / denominator
        if not math.isfinite(value) or value < -1:
            return FlowAdjustedSeries(
                reason="An unreconciled valuation or flow prevents a meaningful return."
            )
        returns.append(value)
    return FlowAdjustedSeries(tuple(days), tuple(returns))


def sharpe(series: FlowAdjustedSeries, risk_free_rate: float = 0.045) -> float | None:
    if series.reason or len(series.returns) < MIN_SHARPE_OBSERVATIONS:
        return None
    mean = sum(series.returns) / len(series.returns)
    variance = sum((r - mean) ** 2 for r in series.returns) / (len(series.returns) - 1)
    if variance <= 1e-16:
        return None
    result = (mean - ((1 + risk_free_rate) ** (1 / 252) - 1)) * math.sqrt(252 / variance)
    return result if math.isfinite(result) else None


def performance_report(  # noqa: PLR0911 - explicit evidence failures
    storage: Any, account_ids: list[str], risk_free_rate: float = 0.045
) -> dict[str, Any]:
    ids = sorted(set(account_ids))
    base = {
        "account_count": len(ids),
        "method": "Daily Modified Dietz; cash flows assumed at mid-day",
        "risk_free_rate": risk_free_rate,
        "risk_free_source": "Fixed planning assumption, not a live Treasury quote",
        "minimum_observations": MIN_SHARPE_OBSERVATIONS,
        "observations": 0,
        "sharpe_ratio": None,
        "cumulative_return": None,
        "start_date": None,
        "end_date": None,
        "benchmark_return": None,
        "benchmark_label": "SPY price return (US large-cap reference; excludes dividends, not a household risk match)",
        "status": "insufficient",
        "detail": "No investment accounts selected.",
    }
    if not ids:
        return base
    with storage.connection() as conn:
        rows = conn.execute(
            """SELECT account_id,snapshot_date,equity FROM portfolio_snapshots
            WHERE account_id=ANY(%s) AND snapshot_date>=CURRENT_DATE-366 AND snapshot_date<CURRENT_DATE
            ORDER BY snapshot_date""",
            [ids],
        ).fetchall()
        accounts = conn.execute(
            """SELECT portfolio_account_id,account_id,metadata->'activity_coverage'
            FROM snaptrade_accounts WHERE portfolio_account_id=ANY(%s) AND is_active=true""",
            [ids],
        ).fetchall()
        market = conn.execute(
            "SELECT date,close FROM day_bars WHERE symbol='SPY' AND date>=CURRENT_DATE-366 AND date<CURRENT_DATE ORDER BY date"
        ).fetchall()
        activities = conn.execute(
            """SELECT sa.portfolio_account_id,ac.trade_date::date,ac.activity_type,ac.amount,ac.currency
            FROM snaptrade_activities ac JOIN snaptrade_accounts sa ON sa.account_id=ac.account_id
            WHERE sa.portfolio_account_id=ANY(%s) AND sa.is_active=true
              AND ac.trade_date>=CURRENT_DATE-366 AND ac.trade_date<CURRENT_DATE""",
            [ids],
        ).fetchall()
    snapshots = {aid: {} for aid in ids}
    for aid, day, equity in rows:
        snapshots[str(aid)][day] = float(equity)
    common = set.intersection(*(set(h) for h in snapshots.values()))
    if len(common) < 2:
        return {
            **base,
            "detail": "The selected accounts need overlapping dated valuations. Adding an account does not count as a return.",
        }
    first, last = min(common), max(common)
    mapped = {}
    for aid, provider_id, coverage in accounts:
        mapped.setdefault(str(aid), []).append((provider_id, coverage))
    for aid in ids:
        sources = mapped.get(aid, [])
        if len(sources) != 1:
            return {
                **base,
                "detail": "Cash-flow coverage is unverified for one or more selected accounts. Sharpe and returns are withheld.",
            }
        coverage = sources[0][1]
        if (
            not isinstance(coverage, dict)
            or not coverage.get("complete")
            or str(coverage.get("from", "9999")) > first.isoformat()
            or str(coverage.get("through", "")) < last.isoformat()
        ):
            return {
                **base,
                "detail": "Complete cash-flow history has not been verified for the valuation period. A successful account activity refresh must cover it before returns can be shown.",
            }
    flows = {}
    for aid, day, raw_kind, amount, currency in activities:
        if not first < day <= last:
            continue
        kind = str(raw_kind or "").upper()
        if currency not in (None, "USD") or kind not in RETURN_ACTIVITY_TYPES | {
            "CONTRIBUTION",
            "WITHDRAWAL",
        }:
            return {
                **base,
                "detail": "An unclassified transfer, activity type, or foreign-currency flow needs reconciliation before returns can be shown.",
            }
        if kind in {"CONTRIBUTION", "WITHDRAWAL"}:
            if amount is None:
                return {**base, "detail": "An external cash flow is missing its amount."}
            flow = abs(float(amount)) * (1 if kind == "CONTRIBUTION" else -1)
            flows[(str(aid), day)] = flows.get((str(aid), day), 0) + flow
    sessions = [
        first + timedelta(days=i)
        for i in range((last - first).days + 1)
        if is_trading_day(first + timedelta(days=i))
    ]
    series = aligned_returns(snapshots, flows, sessions)
    if series.reason:
        return {**base, "detail": series.reason}
    benchmark = dict(market)
    ratio = sharpe(series, risk_free_rate)
    return {
        **base,
        "status": "ready" if ratio is not None else "insufficient_sample",
        "detail": f"{len(series.returns)} aligned trading-day returns across the same {len(ids)} accounts. "
        + (
            "Sharpe requires at least 60 observations and nonzero variation."
            if ratio is None
            else "External contributions and withdrawals are excluded from investment return."
        ),
        "start_date": series.dates[0].isoformat(),
        "end_date": series.dates[-1].isoformat(),
        "observations": len(series.returns),
        "sharpe_ratio": ratio,
        "daily_returns": list(series.returns),
        "cumulative_return": math.prod(1 + r for r in series.returns) - 1,
        "benchmark_return": (float(benchmark[series.dates[-1]]) / float(benchmark[series.dates[0]]) - 1)
            if benchmark.get(series.dates[0], 0) > 0 and benchmark.get(series.dates[-1], 0) > 0 else None,
    }

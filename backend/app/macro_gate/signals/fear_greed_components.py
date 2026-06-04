"""Thin accessors over ``fear_greed_inputs`` for the L1 macro gate.

The VIX, put/call ratio, and HY credit spread series are already ingested
nightly into ``fear_greed_inputs``; the macro gate simply reads from that
table rather than reimplementing fetchers. Normalisation is in
``macro_gate.scoring``.

The put/call writer inserts a row for *every* calendar day (including
weekends and market holidays), but the VIX and HY close series only update on
trading days. To avoid reporting VIX/credit as "missing" on a non-trading day
just because the latest row is a put/call-only skeleton, the daily-after-close
series are coalesced to their most recent non-null observation.

Staleness is judged per-series against its cadence, not merely ``as_of <
latest_row``. HY OAS (FRED ``BAMLH0A0HYM2``) publishes one business day late, so
a one-trading-day lag is its normal cadence, not staleness; ``hy_spread_stale``
only fires once it trails the freshest value that *should* already be published.
VIX is intraday: its daily close is carried-forward (``vix_stale``) whenever it
trails the latest row, because during market hours yesterday's close is not a
current quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from ...logging_config import get_logger
from ...storage.facade import get_storage
from ...utils.market_hours import get_last_trading_day

if TYPE_CHECKING:
    from ...storage._connection_wrapper import PostgreSQLConnectionWrapper

logger = get_logger(__name__)

# Columns eligible for carry-forward coalescing. Hard-coded (never user input)
# so interpolating them into SQL below is safe.
_CARRY_FORWARD_COLUMNS = ("vix_close", "hy_spread")


@dataclass(frozen=True, slots=True)
class FearGreedComponents:
    as_of: date
    vix_close: float | None
    put_call_ratio: float | None
    hy_spread: float | None
    breadth_pct: float | None
    vix_as_of: date | None = None
    hy_spread_as_of: date | None = None
    vix_stale: bool = False
    hy_spread_stale: bool = False


def _latest_non_null(
    conn: PostgreSQLConnectionWrapper, column: str, on_or_before: date | None = None
) -> tuple[float | None, date | None]:
    """Return the most recent non-null ``column`` value and its as-of date."""
    if column not in _CARRY_FORWARD_COLUMNS:
        raise ValueError(f"unexpected carry-forward column: {column}")
    if on_or_before is None:
        row = conn.execute(
            f"""
            SELECT {column}, as_of_date
            FROM fear_greed_inputs
            WHERE {column} IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
        ).fetchone()
    else:
        row = conn.execute(
            f"""
            SELECT {column}, as_of_date
            FROM fear_greed_inputs
            WHERE {column} IS NOT NULL
              AND as_of_date <= %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [on_or_before],
        ).fetchone()
    if row is None or row[0] is None:
        return None, None
    as_of = row[1] if isinstance(row[1], date) else None
    return float(row[0]), as_of


def _expected_credit_floor(reference_date: date) -> date:
    """Oldest as-of the T+1 daily HY credit series can carry within cadence.

    FRED's HY OAS (``BAMLH0A0HYM2``) publishes one business day late: the value
    for trading day D is only available on D+1, so a one-trading-day lag is the
    series' cadence rather than staleness. Allow the credit print to trail the
    most recent trading day by one trading day; anything older than that floor
    is genuinely stale.

    ``reference_date`` is the newest ingested ``fear_greed_inputs`` row, which
    is already ``<= snapshot_date`` on the backtest path, so replay stays
    point-in-time correct and the threshold needs no wall-clock.
    """
    most_recent_trading = get_last_trading_day(reference_date)
    return get_last_trading_day(most_recent_trading - timedelta(days=1))


def _build(
    conn: PostgreSQLConnectionWrapper,
    latest_row: tuple,
    on_or_before: date | None,
) -> FearGreedComponents:
    latest_date = latest_row[0]
    vix_close, vix_as_of = _latest_non_null(conn, "vix_close", on_or_before)
    hy_spread, hy_as_of = _latest_non_null(conn, "hy_spread", on_or_before)
    credit_floor = _expected_credit_floor(latest_date)
    return FearGreedComponents(
        as_of=latest_date,
        vix_close=vix_close,
        put_call_ratio=float(latest_row[1]) if latest_row[1] is not None else None,
        hy_spread=hy_spread,
        breadth_pct=float(latest_row[2]) if latest_row[2] is not None else None,
        vix_as_of=vix_as_of,
        hy_spread_as_of=hy_as_of,
        vix_stale=vix_as_of is not None and vix_as_of < latest_date,
        hy_spread_stale=hy_as_of is not None and hy_as_of < credit_floor,
    )


def fetch_latest() -> FearGreedComponents | None:
    storage = get_storage()
    with storage.connection() as conn:
        latest_row = conn.execute(
            """
            SELECT as_of_date, put_call_ratio, breadth_pct
            FROM fear_greed_inputs
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
        ).fetchone()
        if latest_row is None:
            logger.warning("fear_greed_components_empty")
            return None
        return _build(conn, latest_row, on_or_before=None)


def fetch_on(snapshot_date: date) -> FearGreedComponents | None:
    """Fetch the most recent fear_greed_inputs row on or before ``snapshot_date``.

    Used by the walk-forward backtest to honour ``bar_date <= snapshot_date``.
    """
    storage = get_storage()
    with storage.connection() as conn:
        latest_row = conn.execute(
            """
            SELECT as_of_date, put_call_ratio, breadth_pct
            FROM fear_greed_inputs
            WHERE as_of_date <= %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [snapshot_date],
        ).fetchone()
        if latest_row is None:
            return None
        return _build(conn, latest_row, on_or_before=snapshot_date)

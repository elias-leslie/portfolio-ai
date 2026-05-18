"""S&P 500 breadth — percent of members above their 200-day moving average.

This is the canonical "internal" gauge of the market. Rising breadth >70%
typically accompanies durable rallies; sub-30% accompanies bear markets.

First-run cost is non-trivial (~500 symbols x 250 day_bars); subsequent
daily refreshes are a single rolling-window calculation per symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ...logging_config import get_logger
from ...services import research_universe as universe_service
from ...storage.facade import get_storage

logger = get_logger(__name__)

LOOKBACK_DAYS = 220  # 200 trading days + a buffer for weekends / holidays


@dataclass(frozen=True, slots=True)
class BreadthObservation:
    as_of: date
    universe_size: int
    members_with_data: int
    above_200dma: int
    pct_above_200dma: float


def compute_breadth(as_of: date | None = None) -> BreadthObservation | None:
    """Compute the percent of S&P 500 members trading above their 200d MA.

    ``as_of`` defaults to the latest available bar date across the universe.
    Members with fewer than 200 bars on or before ``as_of`` are skipped (and
    counted separately) so the ratio is honest.
    """
    storage = get_storage()
    symbols = universe_service.list_active_symbols()
    if not symbols:
        logger.warning("spx_breadth_no_universe")
        return None

    with storage.connection() as conn:
        if as_of is None:
            row = conn.execute(
                "SELECT MAX(date) FROM day_bars WHERE symbol = ANY(%s)",
                [symbols],
            ).fetchone()
            if row is None or row[0] is None:
                return None
            as_of_value = row[0]
            if isinstance(as_of_value, datetime):
                as_of = as_of_value.date()
            elif isinstance(as_of_value, date):
                as_of = as_of_value
            else:
                logger.warning("spx_breadth_unexpected_max_date_type", value=as_of_value)
                return None

        rows = conn.execute(
            """
            WITH recent AS (
                SELECT symbol, date, close,
                       ROW_NUMBER() OVER (
                           PARTITION BY symbol ORDER BY date DESC
                       ) AS rn
                FROM day_bars
                WHERE date <= %s::date
                  AND symbol = ANY(%s)
            )
            SELECT symbol,
                   MAX(CASE WHEN rn = 1 THEN close END) AS last_close,
                   AVG(close) FILTER (WHERE rn <= 200) AS ma_200,
                   COUNT(*) FILTER (WHERE rn <= 200) AS bar_count
            FROM recent
            WHERE rn <= %s
            GROUP BY symbol
            """,
            [str(as_of), symbols, LOOKBACK_DAYS],
        ).fetchall()

    members_with_data = 0
    above = 0
    for row in rows:
        last_close = row[1]
        ma_200 = row[2]
        bar_count = row[3] or 0
        if last_close is None or ma_200 is None or bar_count < 200:
            continue
        members_with_data += 1
        if float(last_close) > float(ma_200):
            above += 1

    pct = (above / members_with_data * 100.0) if members_with_data else 0.0
    return BreadthObservation(
        as_of=as_of,
        universe_size=len(symbols),
        members_with_data=members_with_data,
        above_200dma=above,
        pct_above_200dma=pct,
    )


def normalize_to_score(pct_above_200dma: float) -> float:
    """Percent above 200d MA is already on a 0-100 scale.

    We clamp and pass through; the macro gate weights this directly.
    """
    return max(0.0, min(100.0, pct_above_200dma))

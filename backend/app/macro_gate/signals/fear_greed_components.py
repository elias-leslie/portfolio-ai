"""Thin accessors over ``fear_greed_inputs`` for the L1 macro gate.

The VIX, put/call ratio, and HY credit spread series are already ingested
nightly into ``fear_greed_inputs``; the macro gate simply reads from that
table rather than reimplementing fetchers. Normalisation is in
``macro_gate.scoring``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...logging_config import get_logger
from ...storage.facade import get_storage

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FearGreedComponents:
    as_of: date
    vix_close: float | None
    put_call_ratio: float | None
    hy_spread: float | None
    breadth_pct: float | None


def fetch_latest() -> FearGreedComponents | None:
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT as_of_date, vix_close, put_call_ratio, hy_spread, breadth_pct
            FROM fear_greed_inputs
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
        ).fetchone()
    if row is None:
        logger.warning("fear_greed_components_empty")
        return None
    return FearGreedComponents(
        as_of=row[0],
        vix_close=float(row[1]) if row[1] is not None else None,
        put_call_ratio=float(row[2]) if row[2] is not None else None,
        hy_spread=float(row[3]) if row[3] is not None else None,
        breadth_pct=float(row[4]) if row[4] is not None else None,
    )


def fetch_on(snapshot_date: date) -> FearGreedComponents | None:
    """Fetch the most recent fear_greed_inputs row on or before ``snapshot_date``.

    Used by the walk-forward backtest to honour ``bar_date <= snapshot_date``.
    """
    storage = get_storage()
    with storage.connection() as conn:
        row = conn.execute(
            """
            SELECT as_of_date, vix_close, put_call_ratio, hy_spread, breadth_pct
            FROM fear_greed_inputs
            WHERE as_of_date <= %s
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [snapshot_date],
        ).fetchone()
    if row is None:
        return None
    return FearGreedComponents(
        as_of=row[0],
        vix_close=float(row[1]) if row[1] is not None else None,
        put_call_ratio=float(row[2]) if row[2] is not None else None,
        hy_spread=float(row[3]) if row[3] is not None else None,
        breadth_pct=float(row[4]) if row[4] is not None else None,
    )

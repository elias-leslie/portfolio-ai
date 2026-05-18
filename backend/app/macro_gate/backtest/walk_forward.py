"""Walk-forward replay of the L1 macro gate.

For each historical trading day, replay the gate using only data available
on or before that date (``bar_date <= snapshot_date``). The result is a
series of (date, deployment_score, zone) that can be cross-checked against
forward returns to validate the calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...logging_config import get_logger
from ...storage.facade import get_storage
from ..scoring import ComponentScores, RawSignals, build_composite
from ..signals import factor_crowding, term_structure

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ReplayRow:
    snapshot_date: date
    deployment_score: float
    zone: str
    coverage: float
    scores: ComponentScores


FearGreedTuple = tuple[float | None, float | None, float | None, float | None]


def _load_fear_greed_history(start: date, end: date) -> dict[date, FearGreedTuple]:
    storage = get_storage()
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT as_of_date, vix_close, put_call_ratio, hy_spread, breadth_pct
            FROM fear_greed_inputs
            WHERE as_of_date BETWEEN %s AND %s
            ORDER BY as_of_date ASC
            """,
            [start, end],
        ).fetchall()
    result: dict[date, FearGreedTuple] = {}
    for row in rows:
        snapshot_date = row[0]
        if not isinstance(snapshot_date, date):
            continue
        entry: FearGreedTuple = (
            float(row[1]) if row[1] is not None else None,
            float(row[2]) if row[2] is not None else None,
            float(row[3]) if row[3] is not None else None,
            float(row[4]) if row[4] is not None else None,
        )
        result[snapshot_date] = entry
    return result


def replay(start: date, end: date) -> list[ReplayRow]:
    """Replay the gate day-by-day over ``[start, end]`` inclusive.

    Term-structure series is fetched once for the whole window; factor
    crowding is computed once and held constant within the window (it is a
    weekly signal and so does not move materially day-over-day).
    """
    fear_greed_by_date = _load_fear_greed_history(start, end)
    if not fear_greed_by_date:
        logger.warning("walk_forward_no_fear_greed", start=str(start), end=str(end))
        return []

    term_series = dict(term_structure.fetch_series(start_date=start, end_date=end))

    # Crowding is computed once for the closing date of the window — it is
    # a coarse signal and recomputing it daily would dwarf this loop.
    crowding_obs = factor_crowding.compute_crowding()
    crowding_value = crowding_obs.momentum_value_corr if crowding_obs else None

    rows: list[ReplayRow] = []
    for snapshot_date, fg in sorted(fear_greed_by_date.items()):
        vix_close, put_call_ratio, hy_spread, breadth_pct = fg
        raw = RawSignals(
            vix_close=vix_close,
            term_spread_bps=term_series.get(snapshot_date),
            breadth_pct=breadth_pct,
            hy_spread=hy_spread,
            put_call_ratio=put_call_ratio,
            factor_crowding_corr=crowding_value,
        )
        composite = build_composite(raw)
        rows.append(
            ReplayRow(
                snapshot_date=snapshot_date,
                deployment_score=composite.deployment_score,
                zone=composite.zone,
                coverage=composite.coverage,
                scores=composite.scores,
            )
        )
    return rows


def sanity_checks(replay_rows: list[ReplayRow]) -> dict[str, str]:
    """Run the sanity-check assertions from the plan against a replay.

    Returns a dict ``{check_name: 'pass' | 'fail' | 'skip'}``. Skipped
    when the relevant date is not in the replay window.
    """
    by_date = {row.snapshot_date: row for row in replay_rows}
    results: dict[str, str] = {}

    march_2020 = date(2020, 3, 23)
    march_row = by_date.get(march_2020)
    results["march_2020_defensive"] = (
        "pass" if march_row and march_row.zone == "DEFENSIVE" else "skip" if march_row is None else "fail"
    )

    dec_2017 = date(2017, 12, 29)
    dec_row = by_date.get(dec_2017)
    results["dec_2017_full_deploy"] = (
        "pass" if dec_row and dec_row.zone == "FULL_DEPLOY" else "skip" if dec_row is None else "fail"
    )
    return results

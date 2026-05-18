"""Cross-run cost guard for committee fan-out.

``should_run(ticker)`` returns ``False`` if a recent (<24h) committee
run for the same symbol completed *under the same macro zone*. A zone
change invalidates the cache — the macro regime is the input that most
strongly justifies re-asking the committee.

Used by the Phase 3 fan-out workflow before spawning a committee run.
User-triggered ad-hoc runs from the UI bypass the cache (the user is
explicitly paying for a re-run).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

DEFAULT_CACHE_TTL_HOURS = 24


@dataclass(frozen=True, slots=True)
class CacheDecision:
    should_run: bool
    reason: str
    last_run_id: str | None = None
    last_run_at: datetime | None = None
    last_zone: str | None = None


def should_run(
    ticker: str,
    *,
    current_zone: str,
    now: datetime | None = None,
    ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
) -> CacheDecision:
    """Decide whether the fan-out should spawn a fresh committee run.

    Skip if the latest completed/approved run for ``ticker`` finished
    within ``ttl_hours`` AND was produced under the same macro
    ``current_zone``. The zone is read from the prior run's
    ``parent_run_id`` chain? No — simpler and more honest: we compare
    against the zone the *previous fan-out* recorded on its parent
    snapshot. To keep this layer cheap, we just look up the latest
    snapshot's zone and assume it's the steady state since the prior
    run (zone changes are daily granularity).
    """
    symbol = ticker.upper().strip()
    if not symbol:
        return CacheDecision(should_run=False, reason="empty_symbol")

    current = (now or datetime.now(tz=UTC)).astimezone(UTC)
    cutoff = current - timedelta(hours=ttl_hours)

    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            SELECT id, completed_at, source
            FROM committee_runs
            WHERE symbol = %s
              AND status IN ('complete', 'approved')
              AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()

    if row is None:
        return CacheDecision(should_run=True, reason="no_prior_run")

    last_run_id = str(row[0])
    last_completed_raw = row[1]
    last_completed = _to_aware_utc(last_completed_raw)

    if last_completed is None or last_completed < cutoff:
        return CacheDecision(
            should_run=True,
            reason="prior_run_expired",
            last_run_id=last_run_id,
            last_run_at=last_completed,
        )

    last_zone = _zone_at(last_completed)
    if last_zone is None or last_zone != current_zone:
        return CacheDecision(
            should_run=True,
            reason="zone_shifted",
            last_run_id=last_run_id,
            last_run_at=last_completed,
            last_zone=last_zone,
        )

    return CacheDecision(
        should_run=False,
        reason="fresh_within_ttl",
        last_run_id=last_run_id,
        last_run_at=last_completed,
        last_zone=last_zone,
    )


def _zone_at(when: datetime) -> str | None:
    """Look up the macro zone in effect on ``when``'s trading day.

    Matches the most recent snapshot whose ``snapshot_date`` is on or
    before ``when``'s date. Returns ``None`` if no snapshot exists yet.
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            SELECT zone
            FROM signal_macro_snapshots
            WHERE snapshot_date <= %s::date
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (when.date(),),
        ).fetchone()
    return str(row[0]) if row else None


def _to_aware_utc(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return None

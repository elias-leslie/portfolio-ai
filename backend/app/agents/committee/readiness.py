"""Per-symbol data-readiness gate for committee runs.

A deep committee run burns ~9 LLM calls (~$0.30) per symbol and ends
in a typed decision that may trigger a paper trade. If the underlying
data (OHLCV, technical indicators, fundamentals pillar, news) is
missing or stale the analysts hallucinate around emptiness, the
trader sizes off a phantom price, and the audit trail records a
confident but baseless recommendation.

This module is the pre-flight that REFUSES to spend LLM budget on
symbols whose data is not ready. It is a pure, deterministic, query-
only function — no LLM calls, no writes, no side effects — that
returns a structured ``ReadinessReport``.

Callers:
- ``app.api.committee_runs.start_run``        — HTTP 422 with the report
- ``app.workflows.committee_fanout.run_fanout`` — skip BEFORE Tier-1
- ``app.agents.committee.graph.run_committee``  — belt-and-suspenders

Block vs warn:
- ``block`` issues mean the run cannot proceed (e.g. zero OHLCV rows,
  no fresh price, no indicator row).
- ``warn`` issues are recorded for telemetry but do not stop the run
  (e.g. watchlist snapshot present but ``is_stale=true`` and within the
  24h critical window — analysts will downgrade conviction themselves).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.utils.market_hours import get_market_aware_age_hours

logger = get_logger(__name__)


ReadinessSeverity = Literal["block", "warn"]

# Per-check policy ----------------------------------------------------------
# OHLCV / indicators are market data: weekend-aware age is used so a Sunday
# fan-out is not blocked just because Friday's bars are 60h old in calendar
# terms. The thresholds are tighter than the cluster-wide
# data_freshness_service alerts (24h expected) because a committee run that
# happens to be the first to notice missing data should fail fast, not
# silently fall through to LLMs.
_OHLCV_STALE_HOURS = 36
_INDICATOR_STALE_HOURS = 36
# These five together let the technical analyst form a coherent read on
# trend (sma_50/200), momentum (rsi_14, macd), and stop sizing (atr_14).
# Any one missing means the prompt's deliverables can't be honored.
_INDICATOR_REQUIRED_FIELDS: tuple[str, ...] = (
    "rsi_14",
    "macd",
    "atr_14",
    "sma_50",
    "sma_200",
)
# Watchlist scoring refreshes ~every 2h; 6h means at least three refresh
# cycles missed before we hard-block.
_WATCHLIST_SNAPSHOT_BLOCK_HOURS = 6
# Snapshot present but is_stale flag set: warn unless older than critical.
_WATCHLIST_SNAPSHOT_CRITICAL_HOURS = 24
# News: at least one headline within the last week. Tighter "no-news-today"
# checks would false-positive on illiquid names that legitimately have no
# coverage on a given day; 7d catches truly broken ingestion.
_NEWS_RECENCY_DAYS = 7


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    check: str
    severity: ReadinessSeverity
    detail: str
    value: object = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    symbol: str
    ok: bool
    issues: tuple[ReadinessIssue, ...] = field(default_factory=tuple)
    checked_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    @property
    def blocking_issues(self) -> tuple[ReadinessIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "block")

    @property
    def warning_issues(self) -> tuple[ReadinessIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "warn")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "ok": self.ok,
            "issues": [i.to_dict() for i in self.issues],
            "checked_at": self.checked_at.isoformat(),
        }


class CommitteeDataUnreadyError(RuntimeError):
    """Raised when ``assert_committee_ready`` finds blocking issues."""

    def __init__(self, report: ReadinessReport):
        self.report = report
        details = "; ".join(
            f"{i.check}={i.detail}" for i in report.blocking_issues
        ) or "no specific blocker"
        super().__init__(
            f"committee data unready for {report.symbol}: {details}"
        )


def check_committee_readiness(
    symbol: str,
    *,
    now: dt.datetime | None = None,
) -> ReadinessReport:
    """Run every readiness check for ``symbol``. Query-only, no LLM cost.

    Each check runs even if earlier ones failed so the report lists
    every issue at once — UI / logs can show the full picture instead
    of forcing a retry-and-repeat cycle.
    """
    upper_symbol = symbol.upper().strip()
    if not upper_symbol:
        report = ReadinessReport(
            symbol=symbol,
            ok=False,
            issues=(
                ReadinessIssue(
                    check="symbol_invalid",
                    severity="block",
                    detail="empty or whitespace symbol",
                    value=symbol,
                ),
            ),
        )
        return report

    current = now or dt.datetime.now(dt.UTC)
    issues: list[ReadinessIssue] = []
    issues.extend(_check_ohlcv(upper_symbol, current))
    issues.extend(_check_indicators(upper_symbol, current))
    issues.extend(_check_watchlist_snapshot(upper_symbol, current))
    issues.extend(_check_news(upper_symbol, current))

    ok = not any(i.severity == "block" for i in issues)
    return ReadinessReport(
        symbol=upper_symbol,
        ok=ok,
        issues=tuple(issues),
        checked_at=current,
    )


def assert_committee_ready(
    symbol: str,
    *,
    now: dt.datetime | None = None,
) -> ReadinessReport:
    """Raise :class:`CommitteeDataUnreadyError` if the gate fails."""
    report = check_committee_readiness(symbol, now=now)
    if not report.ok:
        raise CommitteeDataUnreadyError(report)
    return report


# ---------- per-check implementations ----------


def _check_ohlcv(symbol: str, now: dt.datetime) -> list[ReadinessIssue]:
    """Block: zero rows or last bar older than the OHLCV stale ceiling.

    Uses ``get_market_aware_age_hours`` so a Sunday fan-out is not
    blocked just because Friday's bars are 60h old in calendar time.
    Also requires the latest row's ``close`` to be a finite positive
    number — a row with NULL close is as good as no row to the trader.
    """
    issues: list[ReadinessIssue] = []
    cm = get_connection_manager()
    try:
        with cm.connection() as conn:
            row = conn.execute(
                """
                SELECT date, close
                FROM day_bars
                WHERE upper(symbol) = upper(%s)
                ORDER BY date DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
    except Exception as exc:
        logger.exception("readiness_ohlcv_query_failed", symbol=symbol)
        return [
            ReadinessIssue(
                check="ohlcv_query_failed",
                severity="block",
                detail=f"day_bars query failed: {exc}",
            )
        ]
    if row is None:
        return [
            ReadinessIssue(
                check="ohlcv_missing",
                severity="block",
                detail="no day_bars row for symbol",
            )
        ]
    last_date, close = row[0], row[1]
    last_update = _date_to_datetime(last_date)
    if last_update is None:
        return [
            ReadinessIssue(
                check="ohlcv_invalid_date",
                severity="block",
                detail=f"last day_bars row has unparseable date={last_date!r}",
            )
        ]
    age = get_market_aware_age_hours(
        last_update=last_update, now=now, is_market_data=True
    )
    if age > _OHLCV_STALE_HOURS:
        issues.append(
            ReadinessIssue(
                check="ohlcv_stale",
                severity="block",
                detail=(
                    f"latest day_bars row is {age:.1f}h old (max {_OHLCV_STALE_HOURS}h)"
                ),
                value=last_update.isoformat(),
            )
        )
    if close is None or not _is_positive_finite(close):
        issues.append(
            ReadinessIssue(
                check="ohlcv_no_price",
                severity="block",
                detail=f"latest day_bars row has close={close!r}",
                value=close,
            )
        )
    return issues


def _check_indicators(symbol: str, now: dt.datetime) -> list[ReadinessIssue]:
    """Block when key indicators are missing or the row is too old.

    The technical analyst prompt promises ATR-sized stops and MA-based
    trend reads; if any of those raw values are NULL the analyst will
    fabricate, so we treat them as required.
    """
    cm = get_connection_manager()
    columns = ", ".join(("date", *_INDICATOR_REQUIRED_FIELDS))
    try:
        with cm.connection() as conn:
            row = conn.execute(
                f"""
                SELECT {columns}
                FROM technical_indicators
                WHERE upper(symbol) = upper(%s)
                ORDER BY date DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
    except Exception as exc:
        logger.exception("readiness_indicators_query_failed", symbol=symbol)
        return [
            ReadinessIssue(
                check="indicators_query_failed",
                severity="block",
                detail=f"technical_indicators query failed: {exc}",
            )
        ]
    if row is None:
        return [
            ReadinessIssue(
                check="indicators_missing",
                severity="block",
                detail="no technical_indicators row for symbol",
            )
        ]
    last_date = row[0]
    last_update = _date_to_datetime(last_date)
    issues: list[ReadinessIssue] = []
    if last_update is None:
        issues.append(
            ReadinessIssue(
                check="indicators_invalid_date",
                severity="block",
                detail=f"latest technical_indicators row has unparseable date={last_date!r}",
            )
        )
    else:
        age = get_market_aware_age_hours(
            last_update=last_update, now=now, is_market_data=True
        )
        if age > _INDICATOR_STALE_HOURS:
            issues.append(
                ReadinessIssue(
                    check="indicators_stale",
                    severity="block",
                    detail=(
                        f"latest technical_indicators row is {age:.1f}h old "
                        f"(max {_INDICATOR_STALE_HOURS}h)"
                    ),
                    value=last_update.isoformat(),
                )
            )
    missing = [
        field_name
        for field_name, value in zip(_INDICATOR_REQUIRED_FIELDS, row[1:], strict=True)
        if value is None
    ]
    if missing:
        issues.append(
            ReadinessIssue(
                check="indicators_incomplete",
                severity="block",
                detail=f"latest row missing required fields: {', '.join(missing)}",
                value=missing,
            )
        )
    return issues


def _check_watchlist_snapshot(symbol: str, now: dt.datetime) -> list[ReadinessIssue]:
    """Block on missing snapshot or too-old snapshot; warn on is_stale flag.

    The snapshot carries the fundamental + catalyst pillar scores the
    committee analysts read. If there is no snapshot at all the
    fundamentals analyst sees an empty payload — that's a block. A
    stale-but-present snapshot is a warn (analyst still has something
    to reason from; the prompt is instructed to downgrade conviction).
    """
    cm = get_connection_manager()
    try:
        with cm.connection() as conn:
            row = conn.execute(
                """
                SELECT s.fetched_at, s.is_stale, s.fundamental_score, s.overall_score
                FROM watchlist_snapshots s
                JOIN watchlist_items i ON i.id = s.item_id
                WHERE upper(i.symbol) = upper(%s)
                ORDER BY s.fetched_at DESC
                LIMIT 1
                """,
                (symbol,),
            ).fetchone()
    except Exception as exc:
        logger.exception("readiness_watchlist_query_failed", symbol=symbol)
        return [
            ReadinessIssue(
                check="watchlist_query_failed",
                severity="block",
                detail=f"watchlist_snapshots query failed: {exc}",
            )
        ]
    if row is None:
        return [
            ReadinessIssue(
                check="watchlist_snapshot_missing",
                severity="block",
                detail="no watchlist_snapshots row for symbol",
            )
        ]
    fetched_at, is_stale_flag, fundamental_score, overall_score = (
        row[0],
        bool(row[1]) if row[1] is not None else False,
        row[2],
        row[3],
    )
    issues: list[ReadinessIssue] = []
    if not isinstance(fetched_at, dt.datetime):
        return [
            ReadinessIssue(
                check="watchlist_snapshot_invalid_time",
                severity="block",
                detail=f"snapshot fetched_at not a datetime: {fetched_at!r}",
            )
        ]
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=dt.UTC)
    age = get_market_aware_age_hours(
        last_update=fetched_at, now=now, is_market_data=False
    )
    if age > _WATCHLIST_SNAPSHOT_CRITICAL_HOURS:
        issues.append(
            ReadinessIssue(
                check="watchlist_snapshot_critical",
                severity="block",
                detail=(
                    f"snapshot is {age:.1f}h old "
                    f"(critical > {_WATCHLIST_SNAPSHOT_CRITICAL_HOURS}h)"
                ),
                value=fetched_at.isoformat(),
            )
        )
    elif age > _WATCHLIST_SNAPSHOT_BLOCK_HOURS:
        issues.append(
            ReadinessIssue(
                check="watchlist_snapshot_stale",
                severity="block",
                detail=(
                    f"snapshot is {age:.1f}h old "
                    f"(max {_WATCHLIST_SNAPSHOT_BLOCK_HOURS}h)"
                ),
                value=fetched_at.isoformat(),
            )
        )
    elif is_stale_flag:
        issues.append(
            ReadinessIssue(
                check="watchlist_is_stale_flag",
                severity="warn",
                detail="snapshot row has is_stale=true",
                value=fetched_at.isoformat(),
            )
        )
    if fundamental_score is None and overall_score is None:
        issues.append(
            ReadinessIssue(
                check="watchlist_no_scores",
                severity="block",
                detail="snapshot has neither fundamental_score nor overall_score",
            )
        )
    return issues


def _check_news(symbol: str, now: dt.datetime) -> list[ReadinessIssue]:
    """Block when there are zero recent news rows in the window.

    The news analyst payload is empty without these. We do not require
    sentiment scoring to be populated on every row — a freshly-fetched
    headline without sentiment is still a real catalyst the analyst
    can describe. But zero rows in 7d means the ingestion is broken
    for this symbol and the analyst would be hallucinating.
    """
    cm = get_connection_manager()
    cutoff = now - dt.timedelta(days=_NEWS_RECENCY_DAYS)
    try:
        with cm.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*), MAX(published_at)
                FROM news_cache
                WHERE upper(symbol) = upper(%s)
                  AND published_at >= %s
                """,
                (symbol, cutoff),
            ).fetchone()
    except Exception as exc:
        logger.exception("readiness_news_query_failed", symbol=symbol)
        return [
            ReadinessIssue(
                check="news_query_failed",
                severity="block",
                detail=f"news_cache query failed: {exc}",
            )
        ]
    count = int(row[0]) if row and row[0] is not None else 0
    last_published = row[1] if row else None
    if count == 0:
        return [
            ReadinessIssue(
                check="news_empty",
                severity="block",
                detail=(
                    f"no news_cache rows for symbol in last {_NEWS_RECENCY_DAYS} days"
                ),
            )
        ]
    # A small heads-up: only one stale-ish article in the window. Not
    # blocking — the news analyst can still produce a deliverable — but
    # worth surfacing.
    if count == 1 and isinstance(last_published, dt.datetime):
        published_age_hours = (now - last_published).total_seconds() / 3600
        if published_age_hours > 72:
            return [
                ReadinessIssue(
                    check="news_sparse",
                    severity="warn",
                    detail=(
                        f"only 1 news row in last {_NEWS_RECENCY_DAYS}d "
                        f"and {published_age_hours:.1f}h old"
                    ),
                    value=last_published.isoformat(),
                )
            ]
    return []


# ---------- small helpers ----------


def _date_to_datetime(value: object) -> dt.datetime | None:
    """Coerce a DATE or DATETIME column value into an aware datetime in UTC.

    DATE values become midnight UTC of that date; this is conservative
    (treats Friday's close as Friday 00:00 UTC) and combines correctly
    with ``get_market_aware_age_hours`` which is internally NY-tz aware.
    """
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.UTC)
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min, tzinfo=dt.UTC)
    return None


def _is_positive_finite(value: object) -> bool:
    import math

    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(as_float):
        return False
    return as_float > 0

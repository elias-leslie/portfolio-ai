"""Forward-catalyst calendar — F4 single source of truth.

Aggregates three event kinds into one ranked list per the plan:

- ``earnings``     — symbol-keyed; cached via ``reference_cache``
- ``ex_dividend``  — symbol-keyed; cached via ``reference_cache``
- ``fomc``         — macro; stored in the dedicated ``fomc_meetings``
                      table refreshed by ``portfolio-catalyst-prewarm``

Every caller (Discovery agent, ``/api/catalysts/upcoming`` router,
``st portfolio catalysts``) imports this service. No catalyst analytics
live anywhere else — that's the SoT contract.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

from app.logging_config import get_logger
from app.portfolio.contracts.catalysts import Catalyst, CatalystKind
from app.watchlist.earnings import (
    fetch_earnings_date_cached,
    fetch_ex_dividend_date_cached,
)

logger = get_logger(__name__)

DEFAULT_KINDS: tuple[CatalystKind, ...] = ("earnings", "ex_dividend", "fomc")
DEFAULT_DAYS = 14
DEFAULT_LIMIT = 20
MAX_DAYS = 365
MAX_LIMIT = 200


class CatalystCalendarService:
    """Build a forward catalyst calendar for the user's portfolio + watchlist.

    The class is a thin orchestrator: per-kind lookups read cached
    sources, then results are merged, sorted by ``date`` ascending, and
    truncated to ``limit``. Any analytics richer than "did this date
    fall in the requested window?" belongs in the per-source helper,
    not here.
    """

    def __init__(self, storage: Any) -> None:
        self.storage = storage

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def upcoming(
        self,
        symbols: Iterable[str] | None = None,
        days: int = DEFAULT_DAYS,
        limit: int = DEFAULT_LIMIT,
        kinds: Iterable[CatalystKind] = DEFAULT_KINDS,
        *,
        include_watchlist: bool = True,
        today: date | None = None,
    ) -> list[Catalyst]:
        """Return upcoming catalysts within ``days`` of ``today``.

        ``symbols`` is the explicit caller-provided universe; when it
        is None the service falls back to the union of
        ``portfolio_positions`` and (optionally) ``watchlist_items``.
        Caps ``days`` and ``limit`` defensively.
        """
        anchor = today or date.today()
        days = max(1, min(days, MAX_DAYS))
        limit = max(1, min(limit, MAX_LIMIT))
        kinds_set = {k for k in kinds if k in DEFAULT_KINDS}
        if not kinds_set:
            kinds_set = set(DEFAULT_KINDS)

        symbol_universe = self._resolve_symbol_universe(
            symbols, include_watchlist=include_watchlist
        )
        cutoff = anchor + timedelta(days=days)

        rows: list[Catalyst] = []
        if "earnings" in kinds_set or "ex_dividend" in kinds_set:
            rows.extend(
                self._symbol_catalysts(
                    symbol_universe, anchor, cutoff, kinds_set
                )
            )
        if "fomc" in kinds_set:
            rows.extend(self._fomc_catalysts(anchor, cutoff))

        rows.sort(key=lambda c: (c.date, c.symbol, c.kind))
        return rows[:limit]

    # ------------------------------------------------------------------
    # universe + per-kind helpers
    # ------------------------------------------------------------------

    def _resolve_symbol_universe(
        self,
        symbols: Iterable[str] | None,
        *,
        include_watchlist: bool,
    ) -> list[str]:
        if symbols is not None:
            seen: set[str] = set()
            out: list[str] = []
            for s in symbols:
                up = (s or "").strip().upper()
                if up and up not in seen:
                    seen.add(up)
                    out.append(up)
            return out

        with self.storage.connection() as conn:
            position_rows = conn.execute(
                "SELECT DISTINCT symbol FROM portfolio_positions"
                " WHERE position_type = 'long' AND shares > 0"
            ).fetchall()
            watchlist_rows: list[Any] = []
            if include_watchlist:
                watchlist_rows = conn.execute(
                    "SELECT DISTINCT symbol FROM watchlist_items"
                ).fetchall()

        seen = set()
        out = []
        for row in (*position_rows, *watchlist_rows):
            sym = (row[0] or "").strip().upper() if row[0] is not None else ""
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
        return out

    def _symbol_catalysts(
        self,
        symbols: list[str],
        anchor: date,
        cutoff: date,
        kinds_set: set[CatalystKind],
    ) -> list[Catalyst]:
        if not symbols:
            return []
        out: list[Catalyst] = []
        with self.storage.connection() as conn:
            for symbol in symbols:
                if "earnings" in kinds_set:
                    earnings = fetch_earnings_date_cached(conn, symbol)
                    cat = _to_catalyst(symbol, "earnings", earnings, anchor, cutoff)
                    if cat is not None:
                        out.append(cat)
                if "ex_dividend" in kinds_set:
                    ex_div = fetch_ex_dividend_date_cached(conn, symbol)
                    cat = _to_catalyst(symbol, "ex_dividend", ex_div, anchor, cutoff)
                    if cat is not None:
                        out.append(cat)
        return out

    def _fomc_catalysts(self, anchor: date, cutoff: date) -> list[Catalyst]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT meeting_date, meeting_type, source FROM fomc_meetings"
                " WHERE meeting_date >= %s AND meeting_date <= %s"
                " ORDER BY meeting_date ASC",
                [anchor.isoformat(), cutoff.isoformat()],
            ).fetchall()
        out: list[Catalyst] = []
        for row in rows:
            meeting_date = _coerce_date(row[0])
            if meeting_date is None:
                continue
            out.append(
                Catalyst(
                    symbol="",
                    kind="fomc",
                    date=meeting_date,
                    days_until=(meeting_date - anchor).days,
                    confirmed=True,
                    source=str(row[2]) if row[2] is not None else "fed",
                    time_of_day=str(row[1]) if row[1] is not None else None,
                )
            )
        return out


# ----------------------------------------------------------------------
# pure helpers (kept module-level for testability)
# ----------------------------------------------------------------------


def _to_catalyst(
    symbol: str,
    kind: CatalystKind,
    raw_date: datetime | None,
    anchor: date,
    cutoff: date,
) -> Catalyst | None:
    if raw_date is None:
        return None
    event_date = raw_date.date() if isinstance(raw_date, datetime) else raw_date
    if event_date < anchor or event_date > cutoff:
        return None
    return Catalyst(
        symbol=symbol,
        kind=kind,
        date=event_date,
        days_until=(event_date - anchor).days,
        confirmed=None,
        source="reference_cache",
    )


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None

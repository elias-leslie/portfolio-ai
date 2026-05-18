"""Research universe service.

Owns the ``research_universe_symbols`` table: refresh from constituent
sources, query active membership for downstream signal collectors and
backtests. Historical departures are preserved with ``removed_at`` so
walk-forward replays can reconstruct point-in-time membership.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..logging_config import get_logger
from ..sources.sp500_constituents import UniverseMember, fetch_sp500_constituents
from ..storage.facade import get_storage

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    added: int
    reactivated: int
    departed: int
    active_count: int
    source: str


def _active_symbols() -> set[str]:
    storage = get_storage()
    df = storage.query(
        "SELECT symbol FROM research_universe_symbols WHERE removed_at IS NULL",
    )
    if df.is_empty():
        return set()
    return {row["symbol"] for row in df.to_dicts()}


def _all_symbols() -> set[str]:
    storage = get_storage()
    df = storage.query("SELECT symbol FROM research_universe_symbols")
    if df.is_empty():
        return set()
    return {row["symbol"] for row in df.to_dicts()}


def refresh_universe(members: Iterable[UniverseMember] | None = None) -> RefreshResult:
    """Reconcile the universe table against the latest constituent list.

    - New members: insert with ``added_at = now()``.
    - Returning members (previously had ``removed_at`` set): clear
      ``removed_at`` and bump ``last_seen_at``.
    - Continuing members: refresh sector/industry/weight and ``last_seen_at``.
    - Departed members (in DB active, not in fetch): set ``removed_at``.

    When ``members`` is None, fetches from primary/fallback sources.
    """
    storage = get_storage()
    if members is None:
        members = fetch_sp500_constituents()
    members_list = list(members)
    if not members_list:
        logger.error("research_universe_refresh_empty")
        return RefreshResult(0, 0, 0, len(_active_symbols()), "none")

    incoming = {m.symbol: m for m in members_list}
    existing_all = _all_symbols()
    existing_active = _active_symbols()
    existing_inactive = existing_all - existing_active

    added = 0
    reactivated = 0
    for symbol, m in incoming.items():
        if symbol in existing_active:
            storage.execute(
                """
                UPDATE research_universe_symbols
                SET source = $1,
                    sector = COALESCE($2, sector),
                    industry = COALESCE($3, industry),
                    weight = COALESCE($4, weight),
                    last_seen_at = now()
                WHERE symbol = $5
                """,
                [m.source, m.sector, m.industry, m.weight, symbol],
            )
        elif symbol in existing_inactive:
            storage.execute(
                """
                UPDATE research_universe_symbols
                SET source = $1,
                    sector = COALESCE($2, sector),
                    industry = COALESCE($3, industry),
                    weight = COALESCE($4, weight),
                    removed_at = NULL,
                    last_seen_at = now()
                WHERE symbol = $5
                """,
                [m.source, m.sector, m.industry, m.weight, symbol],
            )
            reactivated += 1
        else:
            storage.execute(
                """
                INSERT INTO research_universe_symbols
                    (symbol, source, sector, industry, weight)
                VALUES ($1, $2, $3, $4, $5)
                """,
                [symbol, m.source, m.sector, m.industry, m.weight],
            )
            added += 1

    departed_symbols = existing_active - incoming.keys()
    for symbol in departed_symbols:
        storage.execute(
            "UPDATE research_universe_symbols SET removed_at = now() WHERE symbol = $1",
            [symbol],
        )

    active_count = len(_active_symbols())
    result = RefreshResult(
        added=added,
        reactivated=reactivated,
        departed=len(departed_symbols),
        active_count=active_count,
        source=members_list[0].source if members_list else "none",
    )
    logger.info(
        "research_universe_refreshed",
        added=result.added,
        reactivated=result.reactivated,
        departed=result.departed,
        active=result.active_count,
        source=result.source,
    )
    return result


def list_active_symbols() -> list[str]:
    """Return today's active universe symbols ordered alphabetically."""
    storage = get_storage()
    df = storage.query(
        "SELECT symbol FROM research_universe_symbols WHERE removed_at IS NULL ORDER BY symbol",
    )
    if df.is_empty():
        return []
    return [row["symbol"] for row in df.to_dicts()]


def list_active_with_sectors() -> list[dict[str, str | None]]:
    """Return active universe members with sector metadata."""
    storage = get_storage()
    df = storage.query(
        """
        SELECT symbol, sector, industry, weight
        FROM research_universe_symbols
        WHERE removed_at IS NULL
        ORDER BY symbol
        """,
    )
    if df.is_empty():
        return []
    return df.to_dicts()

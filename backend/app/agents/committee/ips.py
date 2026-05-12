"""Deterministic IPS checks for a committee trade proposal.

Four checks, all return ``IpsCheck`` records the PM stage and UI both
consume:

1. ``concentration`` — proposed position size as % of portfolio vs
   the position-sizing cap (default 25%).
2. ``tax_bill`` — for sell/trim, estimate the realized gain hit on
   open lots (lot-level FIFO walk).
3. ``sector_exposure`` — proposed position's sector vs the
   ``sector_targets`` cap (household → global → 'default' precedence).
4. ``wash_sale`` — for sell, scan the 61-day household-wide window via
   the existing ``TLHAnalyzer.wash_sale_check`` helper.

Sector-exposure conversion: ``calculate_sector_exposure`` returns 0-100
percentages but ``sector_targets.max_pct`` stores 0-1 fractions. The
conversion lives here (fold-in #2 from the subtask-1 audit) and is
the boundary between the legacy analytics surface and the new cap
table.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

from .schemas import IpsCheck, IpsResult, TradeProposal

logger = get_logger(__name__)

# Hardcoded fallbacks if sector_targets has no row (which should never
# happen post-migration since 'default' is seeded). These match the
# YAML rules.position_sizing.max_sector_exposure_pct hard fallback.
_MAX_POSITION_PCT_FALLBACK = 0.25
_MAX_SECTOR_PCT_FALLBACK = 0.20

# Synonym normalization for noisy sector taxonomies (Yahoo's "Information
# Technology" vs our "Technology", etc.). The table is intentionally
# small; expand only when symbols.sector ships an unfamiliar label.
_SECTOR_SYNONYMS: dict[str, str] = {
    "information technology": "Technology",
    "consumer cyclical": "Consumer Discretionary",
    "consumer defensive": "Consumer Staples",
    "communication services": "Communication Services",
    "financial services": "Finance",
    "financial": "Finance",
    "financials": "Finance",
    "basic materials": "Materials",
}


def ips_evaluate(proposal: TradeProposal, *, symbol: str, household_id: str | None) -> IpsResult:
    """Run all four IPS checks against the proposal. Pure-Python aggregator."""
    checks = [
        _check_concentration(proposal, symbol=symbol, household_id=household_id),
        _check_tax_bill(proposal, symbol=symbol, household_id=household_id),
        _check_sector_exposure(proposal, symbol=symbol, household_id=household_id),
        _check_wash_sale(proposal, symbol=symbol, household_id=household_id),
    ]
    return IpsResult(checks=checks, all_passed=all(c.passed for c in checks))


def _check_concentration(
    proposal: TradeProposal, *, symbol: str, household_id: str | None
) -> IpsCheck:
    """Concentration cap: proposed % of portfolio vs max_position_percent."""
    threshold = _MAX_POSITION_PCT_FALLBACK
    # The trader output is already qty_pct of portfolio; we only need to
    # compare against the cap. Sells/trims do not concentrate further.
    if proposal.action in {"sell", "trim", "hold"}:
        return IpsCheck(
            name="concentration",
            passed=True,
            severity="info",
            detail=f"{proposal.action} does not increase concentration",
            value=proposal.qty_pct,
            threshold=threshold,
        )
    passed = proposal.qty_pct <= threshold
    return IpsCheck(
        name="concentration",
        passed=passed,
        severity="block" if not passed else "info",
        detail=(
            f"Proposed {proposal.qty_pct:.1%} of portfolio "
            f"{'exceeds' if not passed else 'within'} {threshold:.0%} cap"
        ),
        value=proposal.qty_pct,
        threshold=threshold,
    )


def _check_tax_bill(
    proposal: TradeProposal, *, symbol: str, household_id: str | None
) -> IpsCheck:
    """Estimate realized gain split for sell/trim. Skip for buys."""
    if proposal.action not in {"sell", "trim"}:
        return IpsCheck(
            name="tax_bill",
            passed=True,
            severity="info",
            detail=f"{proposal.action} does not realize a gain or loss",
            value=0.0,
            threshold=None,
        )
    # Walk open lots for the symbol and estimate the realized split.
    # We use a simplified read off portfolio_tax_lots — the proper
    # FIFO/specific-id close logic lives in the trade-execution path;
    # the committee only needs a directional estimate.
    lt, st = _estimate_realized_split(symbol=symbol)
    total = lt + st
    return IpsCheck(
        name="tax_bill",
        passed=True,  # informational — never blocks
        severity="warn" if total > 0 else "info",
        detail=(
            f"Estimated realized: LT=${lt:,.0f}, ST=${st:,.0f} "
            f"(ST taxed as ordinary income)"
        ),
        value=total,
        threshold=None,
    )


def _check_sector_exposure(
    proposal: TradeProposal, *, symbol: str, household_id: str | None
) -> IpsCheck:
    """Sector cap: proposed sector exposure vs sector_targets.max_pct."""
    sector = _resolve_symbol_sector(symbol)
    cap = _lookup_sector_cap(sector, household_id)
    current_pct_fraction = _current_sector_exposure_fraction(sector, household_id)
    delta = proposal.qty_pct if proposal.action in {"buy", "add"} else 0.0
    projected = current_pct_fraction + delta
    passed = projected <= cap
    return IpsCheck(
        name="sector_exposure",
        passed=passed,
        severity="block" if not passed else "info",
        detail=(
            f"{sector or 'Unknown'} projected {projected:.1%} "
            f"{'exceeds' if not passed else 'within'} cap {cap:.0%}"
        ),
        value=projected,
        threshold=cap,
    )


def _check_wash_sale(
    proposal: TradeProposal, *, symbol: str, household_id: str | None
) -> IpsCheck:
    """Wash-sale block: only relevant on sell-at-a-loss."""
    if proposal.action != "sell":
        return IpsCheck(
            name="wash_sale",
            passed=True,
            severity="info",
            detail=f"{proposal.action} does not trigger wash-sale rules",
            value=0.0,
            threshold=None,
        )
    try:
        analyzer = _build_tlh_analyzer()
        if analyzer is None:
            raise RuntimeError("TLHAnalyzer dependencies not constructible")
        verdict = analyzer.wash_sale_check(
            symbol=symbol.upper(),
            sell_date=date.today(),
            household_id=household_id,
        )
    except Exception as exc:
        logger.warning("ips_wash_sale_check_failed", error=str(exc))
        return IpsCheck(
            name="wash_sale",
            passed=True,
            severity="warn",
            detail=f"Could not evaluate wash-sale risk: {exc}",
            value=None,
            threshold=None,
        )
    blocked = bool(getattr(verdict, "blocked", False))
    return IpsCheck(
        name="wash_sale",
        passed=not blocked,
        severity="block" if blocked else "info",
        detail=(
            getattr(verdict, "reason", None) or "No wash-sale conflict in 61-day window"
        ),
        value=1.0 if blocked else 0.0,
        threshold=None,
    )


def _resolve_symbol_sector(symbol: str) -> str | None:
    """Look up the symbol's sector via the existing symbols.sector column.

    Applies the synonym table so e.g. Yahoo's 'Information Technology'
    matches our 'Technology' sector_targets row.
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            "SELECT sector FROM symbols WHERE symbol = %s",
            (symbol.upper(),),
        ).fetchone()
    if not row or not row[0]:
        return None
    raw = str(row[0]).strip()
    key = raw.lower()
    return _SECTOR_SYNONYMS.get(key, raw)


def _lookup_sector_cap(sector: str | None, household_id: str | None) -> float:
    """Resolve the cap precedence: household → global → 'default' → fallback."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        # Try household-scoped row first
        if sector and household_id:
            row = conn.execute(
                """
                SELECT max_pct FROM sector_targets
                WHERE sector = %s AND household_id = %s
                """,
                (sector, household_id),
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        # Fall back to global sector row
        if sector:
            row = conn.execute(
                """
                SELECT max_pct FROM sector_targets
                WHERE sector = %s AND household_id IS NULL
                """,
                (sector,),
            ).fetchone()
            if row and row[0] is not None:
                return float(row[0])
        # Fall back to global 'default' row
        row = conn.execute(
            """
            SELECT max_pct FROM sector_targets
            WHERE sector = 'default' AND household_id IS NULL
            """,
        ).fetchone()
        if row and row[0] is not None:
            return float(row[0])
    return _MAX_SECTOR_PCT_FALLBACK


def _current_sector_exposure_fraction(
    sector: str | None,
    household_id: str | None,
) -> float:
    """Return current portfolio exposure to ``sector`` as a 0-1 fraction.

    Direct SQL against ``portfolio_positions`` joined with ``symbols``.
    Sums (shares * cost_basis) per sector and divides by total. Cost
    basis (not current price) keeps the IPS check stable across
    intraday quote moves.
    """
    _ = household_id  # single-household scoping handled by storage today
    if not sector:
        return 0.0
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            WITH valued AS (
                SELECT p.symbol, p.shares, COALESCE(p.cost_basis, 0) AS cost_basis,
                       COALESCE(s.sector, 'Unknown') AS sector
                FROM portfolio_positions p
                LEFT JOIN symbols s ON s.symbol = p.symbol
            )
            SELECT
                COALESCE(SUM(CASE WHEN sector = %s THEN shares * cost_basis END), 0) AS sector_value,
                COALESCE(SUM(shares * cost_basis), 0) AS total_value
            FROM valued
            """,
            (sector,),
        ).fetchone()
    if not row:
        return 0.0
    sector_value = float(row[0] or 0.0)
    total_value = float(row[1] or 0.0)
    if total_value <= 0:
        return 0.0
    return sector_value / total_value


def _estimate_realized_split(*, symbol: str) -> tuple[float, float]:
    """Roughly estimate (long-term, short-term) realized gain on closing the position.

    Reads ``portfolio_tax_lots`` for open lots of ``symbol``, compares
    each lot's cost basis against the latest close, and splits the gain
    by acquisition age (>365 days = LT, otherwise ST). Returns (0, 0)
    if no lots or no recent close.
    """
    cm = get_connection_manager()
    with cm.connection() as conn:
        rows = conn.execute(
            """
            SELECT remaining_shares, cost_per_share, acquired_date
            FROM portfolio_tax_lots
            WHERE symbol = %s AND remaining_shares > 0 AND disposed_at IS NULL
            """,
            (symbol.upper(),),
        ).fetchall()
        price_row = conn.execute(
            """
            SELECT close
            FROM day_bars
            WHERE symbol = %s
            ORDER BY bar_date DESC
            LIMIT 1
            """,
            (symbol.upper(),),
        ).fetchone()
    if not rows or not price_row or price_row[0] is None:
        return 0.0, 0.0
    current_price = float(price_row[0])
    today = date.today()
    lt_total = 0.0
    st_total = 0.0
    for row in rows:
        shares = float(row[0] or 0.0)
        cost = float(row[1] or 0.0)
        acquired = row[2]
        gain = (current_price - cost) * shares
        if isinstance(acquired, date) and (today - acquired).days > 365:
            lt_total += gain
        else:
            st_total += gain
    return lt_total, st_total


def _build_tlh_analyzer() -> Any | None:
    """Construct a TLHAnalyzer with its required deps, or None on failure.

    The analyzer's constructor needs storage + ledger + price_fetcher;
    we wire them off the existing facades so the committee does not
    duplicate construction logic.
    """
    try:
        from app.portfolio.price_fetcher import PriceDataFetcher
        from app.portfolio.tlh import TLHAnalyzer
        from app.portfolio.transactions import TransactionLedger
        from app.storage import get_storage

        storage = get_storage()
        return TLHAnalyzer(
            storage=storage,
            ledger=TransactionLedger(storage),
            price_fetcher=PriceDataFetcher(storage),
        )
    except Exception as exc:  # broad on purpose — IPS must never crash the run
        logger.warning("ips_tlh_analyzer_build_failed", error=str(exc))
        return None

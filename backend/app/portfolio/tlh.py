"""TLH (tax-loss-harvesting) analyzer — canonical service.

Single source of truth for everything TLH-related:

- ``find_loss_candidates`` — taxable-only positions trading below cost.
- ``wash_sale_check`` — IRS Pub 550 / Rev. Rul. 2008-5 conformant scan
  of the household's 61-day window across spouse and tax-advantaged
  accounts, including substantially-identical ETF equivalents from
  ``tlh_replacements.yaml``.
- ``suggest_replacement`` — YAML lookup for "buy something different"
  recommendations after a loss harvest.

All methods return Pydantic contracts from
``app.portfolio.contracts.tlh``. Internal agents (Jenny / Discovery /
Portfolio Analyzer), the FastAPI router, and ``st portfolio tlh ...``
must consume those contracts directly. Re-deriving any of this math
elsewhere is forbidden by the F1 SoT contract.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .account_types import is_taxable
from .contracts.tlh import (
    ConflictingBuy,
    ReplacementSecurity,
    TLHCandidate,
    WashSaleVerdict,
)
from .price_fetcher import PriceDataFetcher
from .transactions import TransactionLedger

logger = get_logger(__name__)

# IRS wash-sale window: 30 days before and 30 days after the sale date,
# inclusive on both ends. Total of 61 calendar days. Per IRS Pub 550.
_WASH_SALE_DAYS = 30
# Holding-period threshold for long-term capital gains/losses treatment.
# 'Held more than one year' is the precise statutory phrasing.
_LONG_TERM_DAYS = 365


class TLHAnalyzer:
    """Read-only TLH analyzer over the F1 ledger and live prices.

    Lot-aware where ``portfolio_tax_lots`` is populated; falls back to
    the position-level ``portfolio_positions.cost_basis`` aggregate
    when no lots exist (legacy positions). Holding period is best-effort
    from oldest open lot when lots exist; ``None`` otherwise.
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        ledger: TransactionLedger,
        price_fetcher: PriceDataFetcher,
    ) -> None:
        self.storage = storage
        self.ledger = ledger
        self.price_fetcher = price_fetcher

    # ------------------------------------------------------------------
    # candidate scanning
    # ------------------------------------------------------------------

    def find_loss_candidates(
        self,
        *,
        min_loss_pct: float = 0.05,
        min_loss_amount: float = 500.0,
        limit: int = 20,
        detail: bool = False,
    ) -> list[TLHCandidate]:
        """Return long positions in taxable accounts trading below cost.

        ``min_loss_pct`` is a positive fraction interpreted as the
        minimum *magnitude* of loss (a position down 6% qualifies for
        ``min_loss_pct=0.05``). ``min_loss_amount`` is the dollar
        threshold. Both must be met.

        Sorted by largest dollar loss first; clipped to ``limit``. The
        ``detail`` flag controls whether the analyzer populates
        replacement suggestions, holding-period info, and the
        wash-sale check — turning it off keeps the scan cheap.
        """
        if min_loss_pct < 0:
            raise ValueError("min_loss_pct must be a non-negative magnitude")
        if min_loss_amount < 0:
            raise ValueError("min_loss_amount must be a non-negative magnitude")
        if limit <= 0:
            return []

        rows = self._load_taxable_long_positions()
        if not rows:
            return []

        symbols = sorted({row["symbol"] for row in rows})
        prices = self.price_fetcher.fetch_cached_price_data(symbols)

        candidates: list[TLHCandidate] = []
        for row in rows:
            symbol = row["symbol"]
            shares = float(row["shares"])
            cost_per_share = float(row["cost_basis"])
            if shares <= 0 or cost_per_share <= 0:
                continue

            price_info = prices.get(symbol)
            if price_info is None or price_info.error or price_info.price <= 0:
                continue
            current_price = float(price_info.price)
            current_value = current_price * shares
            cost_basis_total = cost_per_share * shares
            unrealized_loss = current_value - cost_basis_total
            if unrealized_loss >= 0:
                continue
            loss_magnitude = -unrealized_loss
            loss_pct = loss_magnitude / cost_basis_total
            if loss_magnitude < min_loss_amount or loss_pct < min_loss_pct:
                continue

            holding_period = None
            realized_lt = 0.0
            realized_st = 0.0
            replacement: ReplacementSecurity | None = None
            wash_blocked = False
            wash_reason: str | None = None

            if detail:
                holding_period = self._holding_period_days(row["account_id"], symbol)
                realized_lt, realized_st = self._loss_split_by_period(
                    account_id=row["account_id"],
                    symbol=symbol,
                    current_price=current_price,
                )
                replacement = self.suggest_replacement(symbol)
                verdict = self.wash_sale_check(
                    symbol=symbol,
                    sell_date=date.today(),
                    household_id=None,
                )
                wash_blocked = verdict.blocked
                wash_reason = verdict.reason

            candidates.append(
                TLHCandidate(
                    symbol=symbol,
                    account_id=str(row["account_id"]),
                    account_type=str(row["account_type"]),
                    shares=shares,
                    cost_basis=cost_per_share,
                    current_price=current_price,
                    current_value=round(current_value, 4),
                    unrealized_loss=round(unrealized_loss, 4),
                    unrealized_loss_pct=round(-loss_pct, 6),
                    holding_period_days=holding_period,
                    realized_loss_long_term=round(realized_lt, 4),
                    realized_loss_short_term=round(realized_st, 4),
                    replacement=replacement,
                    wash_sale_blocked=wash_blocked,
                    wash_sale_reason=wash_reason,
                )
            )

        candidates.sort(key=lambda c: c.unrealized_loss)
        return candidates[:limit]

    # ------------------------------------------------------------------
    # wash-sale detection
    # ------------------------------------------------------------------

    def wash_sale_check(
        self,
        *,
        symbol: str,
        sell_date: date,
        household_id: str | None,
    ) -> WashSaleVerdict:
        """Scan the 61-day window across the household for blocking buys.

        Per IRS Rev. Rul. 2008-5, *all* household-controlled accounts
        count — including spouse accounts and tax-advantaged accounts
        (Roth, IRA, 401k, HSA). The ``household_id`` parameter is
        accepted today as a forward-compat hook; the codebase has a
        single-household model so we currently scan every
        ``portfolio_accounts`` row. Multi-household support in v2 will
        filter by ``household_id`` without changing the contract.
        """
        symbol_upper = symbol.upper()
        accounts = self._all_household_accounts(household_id)
        if not accounts:
            return WashSaleVerdict(
                symbol=symbol_upper,
                sell_date=sell_date,
                household_id=household_id,
                blocked=False,
                reason=None,
                conflicting_buys=[],
                substantially_identical=False,
            )

        account_ids = [acc["id"] for acc in accounts]
        account_type_by_id = {acc["id"]: acc["account_type"] for acc in accounts}

        since = sell_date - timedelta(days=_WASH_SALE_DAYS)
        until = sell_date + timedelta(days=_WASH_SALE_DAYS)

        # Exact-ticker block.
        exact_buys = self.ledger.recent_buys(
            account_ids,
            symbol_upper,
            since_date=since,
            until_date=until,
        )

        # Substantially-identical ETF equivalents (close confidence).
        identical_symbols = _close_equivalents(symbol_upper)
        equivalent_buys: list[Any] = []
        for equiv in identical_symbols:
            equivalent_buys.extend(
                self.ledger.recent_buys(
                    account_ids,
                    equiv,
                    since_date=since,
                    until_date=until,
                )
            )

        conflicts: list[ConflictingBuy] = []
        for txn in exact_buys:
            conflicts.append(
                ConflictingBuy(
                    txn_id=txn.id,
                    account_id=txn.account_id,
                    account_type=str(account_type_by_id.get(txn.account_id, "")),
                    trade_date=txn.trade_date,
                    shares=float(txn.shares),
                    days_offset=(txn.trade_date - sell_date).days,
                )
            )
        for txn in equivalent_buys:
            conflicts.append(
                ConflictingBuy(
                    txn_id=txn.id,
                    account_id=txn.account_id,
                    account_type=str(account_type_by_id.get(txn.account_id, "")),
                    trade_date=txn.trade_date,
                    shares=float(txn.shares),
                    days_offset=(txn.trade_date - sell_date).days,
                )
            )

        substantially_identical = bool(equivalent_buys)
        blocked = bool(conflicts)
        reason: str | None
        if not blocked:
            reason = None
        elif exact_buys and not substantially_identical:
            reason = (
                f"Wash-sale: {len(exact_buys)} buy(s) of {symbol_upper} within "
                f"30 days of {sell_date.isoformat()} across household accounts"
            )
        elif substantially_identical and not exact_buys:
            reason = (
                "Wash-sale risk: substantially identical ETF buy in the 61-day "
                "window — IRS treats close-tracking pairs as identical"
            )
        else:
            reason = (
                "Wash-sale: exact-ticker buys plus substantially identical ETF "
                "buys in the 61-day window"
            )

        return WashSaleVerdict(
            symbol=symbol_upper,
            sell_date=sell_date,
            household_id=household_id,
            blocked=blocked,
            reason=reason,
            conflicting_buys=conflicts,
            substantially_identical=substantially_identical,
        )

    # ------------------------------------------------------------------
    # replacement lookup
    # ------------------------------------------------------------------

    def suggest_replacement(self, symbol: str) -> ReplacementSecurity | None:
        """Return a replacement security for ``symbol`` from the YAML table."""
        return _lookup_replacement(symbol.upper())

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _load_taxable_long_positions(self) -> list[dict[str, Any]]:
        """Load (account_id, account_type, symbol, shares, cost_basis) for taxable accounts."""
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT p.account_id, a.account_type, p.symbol, p.shares,
                       p.cost_basis, p.position_type
                FROM portfolio_positions p
                JOIN portfolio_accounts a ON a.id = p.account_id
                WHERE p.position_type = 'long'
                  AND p.shares > 0
                """
            ).fetchall()

        out: list[dict[str, Any]] = []
        for row in rows:
            account_type = str(row[1])
            if not is_taxable(account_type):
                continue
            out.append(
                {
                    "account_id": str(row[0]),
                    "account_type": account_type,
                    "symbol": str(row[2]).upper(),
                    "shares": row[3],
                    "cost_basis": row[4],
                    "position_type": str(row[5]),
                }
            )
        return out

    def _all_household_accounts(self, household_id: str | None) -> list[dict[str, Any]]:
        """All portfolio accounts the household controls.

        Today the system has a single implicit household so every row
        in ``portfolio_accounts`` qualifies. ``household_id`` is kept
        in the signature so multi-household v2 is a clean drop-in.
        """
        _ = household_id
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, account_type, COALESCE(is_spouse, false)
                FROM portfolio_accounts
                """
            ).fetchall()
        return [
            {
                "id": str(row[0]),
                "account_type": str(row[1]),
                "is_spouse": bool(row[2]),
            }
            for row in rows
        ]

    def _holding_period_days(self, account_id: str, symbol: str) -> int | None:
        """Days held since the *oldest* open lot — most conservative anchor.

        Returns ``None`` when no lots exist (legacy aggregate path).
        """
        lots = self.ledger.open_lots(account_id, symbol)
        if not lots:
            return None
        oldest = min(lot.acquired_date for lot in lots)
        return (date.today() - oldest).days

    def _loss_split_by_period(
        self,
        *,
        account_id: str,
        symbol: str,
        current_price: float,
    ) -> tuple[float, float]:
        """Split unrealized loss into long-term / short-term buckets via lots.

        Returns ``(long_term_loss, short_term_loss)`` as negative
        numbers. Falls back to ``(0.0, 0.0)`` when no lots exist —
        callers downgrade to the aggregate ``unrealized_loss`` field.
        """
        lots = self.ledger.open_lots(account_id, symbol)
        if not lots:
            return 0.0, 0.0

        today = date.today()
        threshold = today - timedelta(days=_LONG_TERM_DAYS)
        lt = 0.0
        st = 0.0
        for lot in lots:
            if lot.remaining_shares <= 0:
                continue
            value = current_price * lot.remaining_shares
            cost = lot.cost_per_share * lot.remaining_shares
            delta = value - cost
            if delta >= 0:
                continue
            if lot.acquired_date < threshold:
                lt += delta
            else:
                st += delta
        return lt, st


# ----------------------------------------------------------------------
# YAML replacement table (module-level, lru_cache)
# ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def _replacement_index() -> dict[str, ReplacementSecurity]:
    """Load tlh_replacements.yaml and index it by from_symbol.

    Pairs are bidirectional: ``A -> B`` defined in YAML auto-derives
    ``B -> A`` so callers can look up either direction.
    """
    raw = (
        resources.files("app.portfolio")
        .joinpath("tlh_replacements.yaml")
        .read_text(encoding="utf-8")
    )
    payload = yaml.safe_load(raw) or {}
    pairs = payload.get("pairs", []) or []
    index: dict[str, ReplacementSecurity] = {}
    for entry in pairs:
        from_sym = str(entry["from_symbol"]).upper()
        to_sym = str(entry["to_symbol"]).upper()
        forward = ReplacementSecurity(
            from_symbol=from_sym,
            to_symbol=to_sym,
            asset_class=str(entry.get("asset_class", "")),
            name=str(entry.get("name", "")),
            rationale=entry.get("rationale"),
            confidence=str(entry.get("confidence", "approximate")),  # type: ignore[arg-type]
        )
        index.setdefault(from_sym, forward)
        reverse = ReplacementSecurity(
            from_symbol=to_sym,
            to_symbol=from_sym,
            asset_class=forward.asset_class,
            name=forward.name,
            rationale=forward.rationale,
            confidence=forward.confidence,
        )
        index.setdefault(to_sym, reverse)
    return index


def _lookup_replacement(symbol: str) -> ReplacementSecurity | None:
    return _replacement_index().get(symbol.upper())


def _close_equivalents(symbol: str) -> list[str]:
    """Return tickers flagged ``confidence='close'`` against ``symbol``.

    Used by the wash-sale check to flag substantially-identical ETF
    buys. Only ``close`` confidence triggers the flag —
    ``approximate`` pairs (different index, similar exposure) are not
    treated as substantially identical.
    """
    index = _replacement_index()
    target = symbol.upper()
    out: list[str] = []
    for from_sym, repl in index.items():
        if repl.confidence != "close":
            continue
        if from_sym == target and repl.to_symbol != target:
            out.append(repl.to_symbol)
    # Dedup in stable order.
    seen: set[str] = set()
    return [s for s in out if not (s in seen or seen.add(s))]

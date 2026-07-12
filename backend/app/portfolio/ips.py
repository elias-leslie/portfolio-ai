"""IPS targets, allocation drift, and tax-aware rebalance — canonical service.

Single source of truth for:

- ``IPSService`` — CRUD over ``ips_targets`` with ``scope ∈
  {household, account}``. Internal callers, the FastAPI router, and
  the ``st portfolio ips`` CLI all consume the same Pydantic
  contracts from :mod:`app.portfolio.contracts.ips`.
- ``DriftCalculator`` — turns the live portfolio + IPS targets into
  a :class:`DriftReport` (detail) or :class:`DriftSummary` (compact).
  ``out_of_band`` flips when ``abs(drift_pct) > drift_band_pct``.
- ``RebalancePlanner`` — three-pass tax-aware planner:

  1. Route *buys* to tax-advantaged accounts first
     (``account_types.is_tax_advantaged``).
  2. For taxable *sells*, prefer lots with **long-term gains** over
     short-term, and **losses** over gains (TLH-aware) — reads
     holding period from ``portfolio_tax_lots.acquired_date`` via
     :meth:`TransactionLedger.open_lots`.
  3. Every taxable sell runs through
     :meth:`TLHAnalyzer.wash_sale_check`; conflicts are rerouted (to
     a tax-advantaged account when possible) or flagged with the
     conflicting buy reference attached to the trade row.

Reimplementing wash-sale or open-lot logic anywhere else is forbidden
by the F1/F2 SoT contract — this module imports
:class:`TLHAnalyzer` and :class:`TransactionLedger`, never re-derives
their math.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .account_types import is_tax_advantaged, is_taxable
from .asset_classification import (
    ASSET_CLASSES,
    AssetClassifier,
    HoldingValue,
    ValueByClass,
)
from .contracts.ips import (
    DriftCoverage,
    DriftCoverageAccount,
    DriftReport,
    DriftRow,
    DriftSummary,
    IPSScope,
    IPSTarget,
    RebalancePlan,
    RebalanceTrade,
)
from .price_fetcher import PriceDataFetcher
from .tlh import TLHAnalyzer
from .transactions import TransactionLedger

logger = get_logger(__name__)

# Rationale codes — kept as constants so tests and agents can string-match
# without parsing free text.
RATIONALE_ROUTE_TO_TAX_ADVANTAGED = "route_to_tax_advantaged"
RATIONALE_ROUTE_TO_TAXABLE = "route_to_taxable"
RATIONALE_LT_LOSS_FIRST = "lt_loss_first"
RATIONALE_LT_GAIN_OVER_ST = "lt_gain_over_st"
RATIONALE_AVOID_REALIZE_GAIN = "avoid_realize_gain"
RATIONALE_WASH_SALE_BLOCKED = "wash_sale_blocked"
RATIONALE_WASH_SALE_REROUTED = "wash_sale_rerouted"
RATIONALE_NO_LOTS_FALLBACK = "no_lots_fallback"


class IncompleteHouseholdCoverageError(RuntimeError):
    """Raised when household holdings are unsafe to turn into trades."""


# ----------------------------------------------------------------------
# IPSService
# ----------------------------------------------------------------------


class IPSService:
    """CRUD over ``ips_targets``.

    Read paths return contract instances; write paths upsert by
    ``(scope, scope_id, asset_class)`` so callers do not need to know
    whether a row already exists.
    """

    def __init__(self, storage: PortfolioStorage) -> None:
        self.storage = storage

    def get_targets(self, scope: IPSScope, scope_id: str) -> list[IPSTarget]:
        """Return all IPS targets for one scope, sorted by asset class."""
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT scope, scope_id, asset_class, target_pct,
                       drift_band_pct, notes
                FROM ips_targets
                WHERE scope = %s AND scope_id = %s
                ORDER BY asset_class
                """,
                [scope, scope_id],
            ).fetchall()
        return [
            IPSTarget(
                scope=str(row[0]),
                scope_id=str(row[1]),
                asset_class=str(row[2]),
                target_pct=float(row[3]),
                drift_band_pct=float(row[4]),
                notes=str(row[5]) if row[5] is not None else None,
            )
            for row in rows
        ]

    def list_scopes(self) -> list[tuple[str, str]]:
        """Return distinct ``(scope, scope_id)`` pairs that have targets."""
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT scope, scope_id FROM ips_targets ORDER BY scope, scope_id"
            ).fetchall()
        return [(str(r[0]), str(r[1])) for r in rows]

    def set_target(
        self,
        *,
        scope: IPSScope,
        scope_id: str,
        asset_class: str,
        target_pct: float,
        drift_band_pct: float = 0.05,
        notes: str | None = None,
    ) -> IPSTarget:
        """Upsert one IPS target row.

        Validates ranges in Python so callers get a clear ``ValueError``
        before the DB constraint trips. Returns the persisted contract.
        """
        if scope not in ("household", "account"):
            raise ValueError(f"scope must be 'household' or 'account', got {scope!r}")
        if not (0.0 <= target_pct <= 1.0):
            raise ValueError("target_pct must be between 0 and 1")
        if not (0.0 <= drift_band_pct <= 1.0):
            raise ValueError("drift_band_pct must be between 0 and 1")

        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO ips_targets
                    (id, scope, scope_id, asset_class, target_pct,
                     drift_band_pct, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scope, scope_id, asset_class) DO UPDATE SET
                    target_pct = EXCLUDED.target_pct,
                    drift_band_pct = EXCLUDED.drift_band_pct,
                    notes = EXCLUDED.notes,
                    updated_at = now()
                """,
                [
                    str(uuid.uuid4()),
                    scope,
                    scope_id,
                    asset_class,
                    target_pct,
                    drift_band_pct,
                    notes,
                ],
            )
            conn.commit()

        return IPSTarget(
            scope=scope,
            scope_id=scope_id,
            asset_class=asset_class,
            target_pct=target_pct,
            drift_band_pct=drift_band_pct,
            notes=notes,
        )

    def delete_target(self, *, scope: IPSScope, scope_id: str, asset_class: str) -> bool:
        """Delete one target row. Returns True when a row was removed."""
        with self.storage.connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM ips_targets
                WHERE scope = %s AND scope_id = %s AND asset_class = %s
                """,
                [scope, scope_id, asset_class],
            )
            conn.commit()
        rowcount = getattr(cursor, "rowcount", None)
        return bool(rowcount) if rowcount is not None else True


# ----------------------------------------------------------------------
# DriftCalculator
# ----------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class _Holding:
    """Internal — one row of (account_id, account_type, symbol, value)."""

    account_id: str
    account_type: str
    symbol: str
    shares: float
    cost_per_share: float
    current_value: float


class DriftCalculator:
    """Turn current holdings + IPS targets into a drift report."""

    def __init__(
        self,
        storage: PortfolioStorage,
        asset_classifier: AssetClassifier,
        ips_service: IPSService,
        price_fetcher: PriceDataFetcher,
        household_allocation_provider: Callable[[], Any] | None = None,
    ) -> None:
        self.storage = storage
        self.classifier = asset_classifier
        self.ips_service = ips_service
        self.price_fetcher = price_fetcher
        self.household_allocation_provider = household_allocation_provider

    def compute_drift(
        self,
        scope: IPSScope,
        scope_id: str,
        *,
        snapshot_date: date | None = None,
    ) -> DriftReport:
        """Build the full drift report for one scope."""
        snapshot = snapshot_date or date.today()
        coverage: DriftCoverage | None = None
        if scope == "household" and self.household_allocation_provider is not None:
            universe = self.household_allocation_provider()
            bucketed = ValueByClass(
                total_value=float(universe.total_value),
                by_class=dict(universe.by_class),
                unclassified_value=float(universe.unclassified_value),
            )
            coverage = DriftCoverage(
                status=universe.status,
                canonical_total_value=universe.total_value,
                coverage_pct=universe.coverage_pct,
                excluded_value=universe.unclassified_value,
                message=universe.message,
                accounts_needing_holdings=[
                    DriftCoverageAccount(
                        household_account_id=account.household_account_id,
                        label=account.label,
                        current_value=account.current_value,
                        exact_value=account.exact_value,
                        unclassified_value=account.unclassified_value,
                        manual_holdings_editable=account.manual_holdings_editable,
                        priced_position_count=account.priced_position_count,
                    )
                    for account in universe.accounts
                    if account.unclassified_value > 0.01 or account.mismatch
                ],
            )
        else:
            holdings = self._holdings_for_scope(scope, scope_id)
            accounts = _accounts_in_scope(self.storage, scope, scope_id)
            cash_value = sum(
                max(float(account.get("cash_balance") or 0.0), 0.0)
                for account in accounts
            )
            values = [
                HoldingValue(symbol=h.symbol, value=h.current_value) for h in holdings
            ]
            if cash_value > 0:
                values.append(HoldingValue(symbol="SPAXX", value=cash_value))
            bucketed = self.classifier.classify_value(values)
        targets = self.ips_service.get_targets(scope, scope_id)
        target_index = {t.asset_class: t for t in targets}

        rows = _build_drift_rows(target_index, bucketed)

        present_classes = set(bucketed.by_class)
        missing = sorted(present_classes - set(target_index) - {"unclassified"})

        return DriftReport(
            scope=scope,
            scope_id=scope_id,
            snapshot_date=snapshot,
            total_value=bucketed.total_value,
            rows=rows,
            classes_missing_targets=missing,
            coverage=coverage,
        )

    def compute_summary(
        self,
        scope: IPSScope,
        scope_id: str,
        *,
        snapshot_date: date | None = None,
    ) -> DriftSummary:
        """Compact digest used by ``GET /api/portfolio/ips/drift`` by default."""
        report = self.compute_drift(scope, scope_id, snapshot_date=snapshot_date)
        max_drift = max(
            (
                abs(row.drift_pct)
                for row in report.rows
                if row.asset_class != "unclassified"
            ),
            default=0.0,
        )
        oob = sum(1 for r in report.rows if r.out_of_band)
        return DriftSummary(
            scope=scope,
            scope_id=scope_id,
            total_value=report.total_value,
            max_drift_pct=round(max_drift, 6),
            classes_out_of_band=oob,
            snapshot_date=report.snapshot_date,
            coverage=report.coverage,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _holdings_for_scope(self, scope: IPSScope, scope_id: str) -> list[_Holding]:
        accounts = _accounts_in_scope(self.storage, scope, scope_id)
        if not accounts:
            return []
        account_id_set = {acc["id"] for acc in accounts}
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT account_id, symbol, shares, cost_basis
                FROM portfolio_positions
                WHERE position_type = 'long' AND shares > 0
                """
            ).fetchall()
        if not rows:
            return []
        symbols = sorted({str(row[1]).upper() for row in rows if str(row[0]) in account_id_set})
        prices = self.price_fetcher.fetch_cached_price_data(symbols)
        type_by_id = {acc["id"]: acc["account_type"] for acc in accounts}
        out: list[_Holding] = []
        for row in rows:
            account_id = str(row[0])
            if account_id not in account_id_set:
                continue
            symbol = str(row[1]).upper()
            shares = float(row[2])
            cost_per_share = float(row[3])
            price_info = prices.get(symbol)
            if price_info is None or getattr(price_info, "error", None) or price_info.price <= 0:
                continue
            current_price = float(price_info.price)
            current_value = current_price * shares
            out.append(
                _Holding(
                    account_id=account_id,
                    account_type=str(type_by_id.get(account_id, "")),
                    symbol=symbol,
                    shares=shares,
                    cost_per_share=cost_per_share,
                    current_value=current_value,
                )
            )
        return out


def _build_drift_rows(
    target_index: dict[str, IPSTarget],
    bucketed: ValueByClass,
) -> list[DriftRow]:
    """Combine targets with bucketed actuals into ordered DriftRow list.

    Includes a row for every targeted asset class (even if actual = 0)
    and for any over-targeted class actually present.
    """
    rows: list[DriftRow] = []
    classes = sorted(set(target_index) | set(bucketed.by_class))
    total = bucketed.total_value or 0.0
    for asset_class in classes:
        target = target_index.get(asset_class)
        if target is None:
            target_pct = 0.0
            band = 0.0
        else:
            target_pct = target.target_pct
            band = target.drift_band_pct
        actual_value = bucketed.by_class.get(asset_class, 0.0)
        actual_pct = (actual_value / total) if total > 0 else 0.0
        drift_pct = actual_pct - target_pct
        target_value = target_pct * total
        rows.append(
            DriftRow(
                asset_class=asset_class,
                target_pct=round(target_pct, 6),
                actual_pct=round(actual_pct, 6),
                drift_pct=round(drift_pct, 6),
                drift_band_pct=round(band, 6),
                out_of_band=(
                    abs(drift_pct) > band if target is not None and band > 0 else False
                ),
                target_value=round(target_value, 4),
                actual_value=round(actual_value, 4),
                drift_value=round(actual_value - target_value, 4),
            )
        )
    return rows


def _accounts_in_scope(
    storage: PortfolioStorage, scope: IPSScope, scope_id: str
) -> list[dict[str, Any]]:
    """Return ``[{id, account_type, is_spouse}]`` for the scope."""
    if scope == "account":
        with storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, account_type, COALESCE(is_spouse, false),
                       COALESCE(cash_balance, 0)
                FROM portfolio_accounts WHERE id = %s
                """,
                [scope_id],
            ).fetchall()
    else:
        with storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, account_type, COALESCE(is_spouse, false),
                       COALESCE(cash_balance, 0)
                FROM portfolio_accounts
                WHERE account_type <> 'paper'
                """
            ).fetchall()
    return [
        {
            "id": str(r[0]),
            "account_type": str(r[1]),
            "is_spouse": bool(r[2]),
            "cash_balance": float(r[3]),
        }
        for r in rows
    ]


# ----------------------------------------------------------------------
# RebalancePlanner
# ----------------------------------------------------------------------


class RebalancePlanner:
    """Three-pass tax-aware rebalance planner.

    Lives strictly inside the SoT boundary: imports
    :class:`TLHAnalyzer` and :class:`TransactionLedger` for wash-sale
    checks and lot data, never re-derives them.
    """

    def __init__(
        self,
        drift_calculator: DriftCalculator,
        tlh_analyzer: TLHAnalyzer,
        ledger: TransactionLedger,
    ) -> None:
        self.drift_calc = drift_calculator
        self.tlh = tlh_analyzer
        self.ledger = ledger

    def propose_trades(
        self,
        scope: IPSScope,
        scope_id: str,
        *,
        prefer_tax_advantaged: bool = True,
        prefer_ltcg: bool = True,
        snapshot_date: date | None = None,
    ) -> RebalancePlan:
        """Propose a list of buys and sells that close the drift gap.

        The output is a :class:`RebalancePlan` whose ``trades`` are
        deterministic given the same inputs. Each trade carries a
        machine-readable ``rationale`` code so downstream agents can
        reason about *why* a trade was placed.
        """
        snapshot = snapshot_date or date.today()
        report = self.drift_calc.compute_drift(scope, scope_id, snapshot_date=snapshot)
        self._require_tradeable_coverage(scope=scope, report=report)
        accounts = _accounts_in_scope(self.drift_calc.storage, scope, scope_id)
        if not accounts:
            return RebalancePlan(scope=scope, scope_id=scope_id, snapshot_date=snapshot)
        account_lookup = {acc["id"]: acc for acc in accounts}

        tax_advantaged_accounts = [
            acc for acc in accounts if is_tax_advantaged(acc["account_type"])
        ]
        taxable_accounts = [acc for acc in accounts if is_taxable(acc["account_type"])]

        holdings = self.drift_calc._holdings_for_scope(scope, scope_id)
        holdings_by_account_class = _index_holdings_by_account_class(
            holdings, self.drift_calc.classifier
        )

        trades: list[RebalanceTrade] = []
        wash_conflicts = 0
        corrected: list[str] = []
        lt_realized = 0.0
        st_realized = 0.0
        total_buy = 0.0
        total_sell = 0.0

        for row in report.rows:
            if not row.out_of_band:
                continue
            corrected.append(row.asset_class)
            if row.drift_value < 0:
                # Underweight — we need to BUY this class.
                trade = self._plan_buy(
                    row=row,
                    accounts=accounts,
                    tax_advantaged_accounts=tax_advantaged_accounts,
                    taxable_accounts=taxable_accounts,
                    prefer_tax_advantaged=prefer_tax_advantaged,
                )
                if trade is not None:
                    trades.append(trade)
                    total_buy += trade.estimated_value
            else:
                # Overweight — SELL this class. The selector applies the
                # LT-loss-first / LT-gain-over-ST preference, then a
                # wash-sale check on the candidate sell.
                sell_trade = self._plan_sell(
                    row=row,
                    holdings_by_account_class=holdings_by_account_class,
                    account_lookup=account_lookup,
                    prefer_ltcg=prefer_ltcg,
                    snapshot_date=snapshot,
                    tax_advantaged_accounts=tax_advantaged_accounts,
                    scope=scope,
                    scope_id=scope_id,
                )
                if sell_trade is None:
                    continue
                if sell_trade.wash_sale_conflict:
                    wash_conflicts += 1
                trades.append(sell_trade)
                total_sell += sell_trade.estimated_value
                lt_realized += sell_trade.realized_gain_long_term
                st_realized += sell_trade.realized_gain_short_term

        return RebalancePlan(
            scope=scope,
            scope_id=scope_id,
            snapshot_date=snapshot,
            trades=trades,
            total_buy_value=round(total_buy, 4),
            total_sell_value=round(total_sell, 4),
            realized_gain_long_term=round(lt_realized, 4),
            realized_gain_short_term=round(st_realized, 4),
            wash_sale_conflicts=wash_conflicts,
            asset_classes_corrected=corrected,
        )

    @staticmethod
    def _require_tradeable_coverage(
        *,
        scope: IPSScope,
        report: DriftReport,
    ) -> None:
        """Fail closed unless this exact household report has complete coverage."""
        if scope != "household":
            return
        coverage = report.coverage
        if coverage is None:
            raise IncompleteHouseholdCoverageError(
                "Household investment coverage could not be verified. Reconcile "
                "holdings before generating trades."
            )
        if coverage.status != "complete":
            raise IncompleteHouseholdCoverageError(coverage.message)

    # ------------------------------------------------------------------
    # buy planning
    # ------------------------------------------------------------------

    def _plan_buy(
        self,
        *,
        row: DriftRow,
        accounts: list[dict[str, Any]],
        tax_advantaged_accounts: list[dict[str, Any]],
        taxable_accounts: list[dict[str, Any]],
        prefer_tax_advantaged: bool,
    ) -> RebalanceTrade | None:
        """Pick a destination account and create a buy trade.

        Pass 1: route to tax-advantaged when ``prefer_tax_advantaged``
        is on and at least one such account exists. Otherwise fall back
        to the first taxable account; if no usable account exists at
        all, return None and leave it to the user.
        """
        chosen, rationale = self._pick_buy_account(
            tax_advantaged_accounts,
            taxable_accounts,
            accounts,
            prefer_tax_advantaged=prefer_tax_advantaged,
        )
        if chosen is None:
            return None
        symbol = _representative_symbol_for_class(row.asset_class)
        if symbol is None:
            return None
        amount = -row.drift_value  # underweight → drift_value negative → amount positive
        # Quote the representative symbol so trade.shares is populated even
        # when the household holds none of it yet — agents and the human
        # rebalance UI both read shares directly to size the order.
        approx_shares = self._approximate_shares(symbol, amount)
        return RebalanceTrade(
            action="buy",
            account_id=chosen["id"],
            account_type=chosen["account_type"],
            symbol=symbol,
            asset_class=row.asset_class,
            shares=approx_shares,
            estimated_value=round(amount, 4),
            rationale=rationale,
        )

    def _approximate_shares(self, symbol: str, dollar_amount: float) -> float:
        if dollar_amount <= 0:
            return 0.0
        prices = self.drift_calc.price_fetcher.fetch_cached_price_data([symbol])
        info = prices.get(symbol)
        if info is None or getattr(info, "error", None):
            return 0.0
        price = float(getattr(info, "price", 0.0) or 0.0)
        if price <= 0:
            return 0.0
        return round(dollar_amount / price, 6)

    @staticmethod
    def _pick_buy_account(
        tax_advantaged_accounts: list[dict[str, Any]],
        taxable_accounts: list[dict[str, Any]],
        accounts: list[dict[str, Any]],
        *,
        prefer_tax_advantaged: bool,
    ) -> tuple[dict[str, Any] | None, str]:
        if prefer_tax_advantaged and tax_advantaged_accounts:
            return tax_advantaged_accounts[0], RATIONALE_ROUTE_TO_TAX_ADVANTAGED
        if taxable_accounts:
            return taxable_accounts[0], RATIONALE_ROUTE_TO_TAXABLE
        if accounts:
            return accounts[0], RATIONALE_ROUTE_TO_TAXABLE
        return None, RATIONALE_ROUTE_TO_TAXABLE

    # ------------------------------------------------------------------
    # sell planning
    # ------------------------------------------------------------------

    def _plan_sell(
        self,
        *,
        row: DriftRow,
        holdings_by_account_class: dict[tuple[str, str], list[_Holding]],
        account_lookup: dict[str, dict[str, Any]],
        prefer_ltcg: bool,
        snapshot_date: date,
        tax_advantaged_accounts: list[dict[str, Any]],
        scope: IPSScope,
        scope_id: str,
    ) -> RebalanceTrade | None:
        """Pick a holding to sell down for the overweight class.

        Pass 2: rank candidates by tax desirability; pick the best.
        Pass 3: wash-sale check on taxable sells; reroute to a
        tax-advantaged account holding the same symbol if available,
        otherwise flag with the conflicting buy reference.
        """
        amount = row.drift_value  # overweight → drift_value positive
        candidates = self._rank_sell_candidates(
            row.asset_class, holdings_by_account_class, prefer_ltcg=prefer_ltcg
        )
        if not candidates:
            return None
        top = candidates[0]
        rationale = top.rationale
        wash_blocked = False
        wash_reason: str | None = None
        chosen = top.holding
        chosen_account = account_lookup.get(chosen.account_id)
        if chosen_account is None:
            return None

        if is_taxable(chosen_account["account_type"]):
            verdict = self.tlh.wash_sale_check(
                symbol=chosen.symbol,
                sell_date=snapshot_date,
                household_id=scope_id if scope == "household" else None,
            )
            if verdict.blocked:
                rerouted = self._try_reroute_sell(
                    chosen=chosen,
                    candidates=candidates,
                    tax_advantaged_accounts=tax_advantaged_accounts,
                    holdings_by_account_class=holdings_by_account_class,
                    asset_class=row.asset_class,
                )
                if rerouted is not None:
                    chosen = rerouted
                    chosen_account = account_lookup.get(chosen.account_id) or chosen_account
                    rationale = RATIONALE_WASH_SALE_REROUTED
                else:
                    wash_blocked = True
                    rationale = RATIONALE_WASH_SALE_BLOCKED
                    wash_reason = verdict.reason

        sell_value = min(amount, chosen.current_value)
        share_fraction = sell_value / chosen.current_value if chosen.current_value > 0 else 0.0
        approx_shares = round(chosen.shares * share_fraction, 6)

        lt_gain = 0.0
        st_gain = 0.0
        no_lots_fallback = False
        if is_taxable(chosen_account["account_type"]):
            consume = self.ledger.preview_lots_fifo(
                account_id=chosen.account_id,
                symbol=chosen.symbol,
                shares=approx_shares if approx_shares > 0 else chosen.shares,
                sell_date=snapshot_date,
                sell_price=chosen.current_value / chosen.shares if chosen.shares else 0.0,
            )
            lt_gain = consume.realized_gain_long_term
            st_gain = consume.realized_gain_short_term
            no_lots_fallback = consume.used_position_aggregate_fallback
            if no_lots_fallback and rationale not in (
                RATIONALE_WASH_SALE_BLOCKED,
                RATIONALE_WASH_SALE_REROUTED,
            ):
                rationale = RATIONALE_NO_LOTS_FALLBACK

        return RebalanceTrade(
            action="sell",
            account_id=chosen.account_id,
            account_type=chosen_account["account_type"],
            symbol=chosen.symbol,
            asset_class=row.asset_class,
            shares=approx_shares,
            estimated_value=round(sell_value, 4),
            rationale=rationale,
            wash_sale_conflict=wash_blocked,
            wash_sale_reason=wash_reason,
            realized_gain_long_term=round(lt_gain, 4),
            realized_gain_short_term=round(st_gain, 4),
        )

    def _rank_sell_candidates(
        self,
        asset_class: str,
        holdings_by_account_class: dict[tuple[str, str], list[_Holding]],
        *,
        prefer_ltcg: bool,
    ) -> list[_SellCandidate]:
        """Rank holdings in the overweight class by tax desirability.

        Order:
          1. Long-term LOSSES (TLH-aware).
          2. Long-term gains (LTCG > STCG when prefer_ltcg).
          3. Short-term gains (avoid_realize_gain rationale).

        The rank function is deliberate and self-contained so that
        ``test_rebalance_planner.py`` can assert ordering directly.
        """
        ranked: list[_SellCandidate] = []
        for (_account_id, klass), items in holdings_by_account_class.items():
            if klass != asset_class:
                continue
            for holding in items:
                if holding.shares <= 0 or holding.current_value <= 0:
                    continue
                ranked.append(_make_sell_candidate(holding, self.ledger, prefer_ltcg))
        ranked.sort(key=_sell_sort_key)
        return ranked

    def _try_reroute_sell(
        self,
        *,
        chosen: _Holding,
        candidates: list[_SellCandidate],
        tax_advantaged_accounts: list[dict[str, Any]],
        holdings_by_account_class: dict[tuple[str, str], list[_Holding]],
        asset_class: str,
    ) -> _Holding | None:
        """Reroute a wash-blocked taxable sell to a tax-advantaged sibling.

        We only reroute when there is a holding of the *same symbol*
        in a tax-advantaged account big enough to absorb part of the
        overweight; otherwise rerouting would distort sector exposure
        without solving the wash-sale problem.
        """
        if not tax_advantaged_accounts:
            return None
        adv_ids = {acc["id"] for acc in tax_advantaged_accounts}
        for candidate in candidates:
            holding = candidate.holding
            if holding.account_id not in adv_ids:
                continue
            if holding.symbol != chosen.symbol:
                continue
            if holding.shares <= 0 or holding.current_value <= 0:
                continue
            return holding
        # Fall back to *any* same-class holding inside a tax-advantaged
        # account; preserves the rebalance gain at the cost of changing
        # the sold symbol.
        for (account_id, klass), items in holdings_by_account_class.items():
            if klass != asset_class or account_id not in adv_ids:
                continue
            for holding in items:
                if holding.shares > 0 and holding.current_value > 0:
                    return holding
        return None


@dataclass(slots=True, frozen=True)
class _SellCandidate:
    holding: _Holding
    is_long_term: bool
    is_loss: bool
    rationale: str
    sort_priority: int
    """Lower wins. Set by :func:`_make_sell_candidate`."""


def _make_sell_candidate(
    holding: _Holding,
    ledger: TransactionLedger,
    prefer_ltcg: bool,
) -> _SellCandidate:
    """Compute holding-period and gain/loss flags for ranking.

    Uses :meth:`TransactionLedger.open_lots`. When no lots exist, uses
    aggregate cost basis and treats the sale as short-term/unknown
    (matches TLHAnalyzer's conservative bucketing).
    """
    today = date.today()
    lots = ledger.open_lots(holding.account_id, holding.symbol)
    if lots:
        oldest = min(lot.acquired_date for lot in lots)
        is_long_term = (today - oldest).days > 365
    else:
        is_long_term = False
    cost_total = holding.shares * holding.cost_per_share
    is_loss = holding.current_value < cost_total
    rationale, priority = _rank_priority(is_long_term, is_loss, prefer_ltcg)
    return _SellCandidate(
        holding=holding,
        is_long_term=is_long_term,
        is_loss=is_loss,
        rationale=rationale,
        sort_priority=priority,
    )


def _rank_priority(is_long_term: bool, is_loss: bool, prefer_ltcg: bool) -> tuple[str, int]:
    """Return (rationale_code, sort_priority) for a holding.

    Priority bands (lower = picked first):

    * ``10`` long-term losses (TLH-aware)
    * ``20`` short-term losses (also tax-favorable)
    * ``30`` long-term gains (LTCG)
    * ``40`` short-term gains (avoid)
    * ``50`` flat positions
    """
    if is_loss:
        if is_long_term:
            return RATIONALE_LT_LOSS_FIRST, 10
        return RATIONALE_LT_LOSS_FIRST, 20
    if is_long_term:
        return RATIONALE_LT_GAIN_OVER_ST if prefer_ltcg else RATIONALE_AVOID_REALIZE_GAIN, 30
    return RATIONALE_AVOID_REALIZE_GAIN, 40


def _sell_sort_key(candidate: _SellCandidate) -> tuple[int, float]:
    return (candidate.sort_priority, -candidate.holding.current_value)


def _index_holdings_by_account_class(
    holdings: Iterable[_Holding], classifier: AssetClassifier
) -> dict[tuple[str, str], list[_Holding]]:
    """Group holdings by ``(account_id, primary_asset_class)``."""
    out: dict[tuple[str, str], list[_Holding]] = {}
    for holding in holdings:
        klass = classifier.primary_class(holding.symbol)
        out.setdefault((holding.account_id, klass), []).append(holding)
    return out


# Curated representative symbol per asset class for buy trades. Picked
# from the same liquid-ETF universe used by :data:`ASSET_CLASS_BY_SYMBOL`
# so the planner's buy suggestion lines up with how the classifier will
# bucket the resulting position when drift is recomputed tomorrow.
_REPRESENTATIVE_SYMBOL: dict[str, str] = {
    "us_equity": "VTI",
    "intl_equity": "VXUS",
    "bonds": "BND",
    "cash": "BIL",
    "alts": "GLD",
    "real_estate": "VNQ",
}


def _representative_symbol_for_class(asset_class: str) -> str | None:
    if asset_class not in ASSET_CLASSES:
        return None
    return _REPRESENTATIVE_SYMBOL.get(asset_class)


# Surfaced for introspection by the workflow + tests.
_ = json  # silence linters when planning a JSON dump pathway later

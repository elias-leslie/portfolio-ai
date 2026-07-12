"""Transaction ledger service for the portfolio.

The TransactionLedger is the canonical service layer for everything that
queries the buy/sell/dividend history of a portfolio: TLH candidates,
wash-sale detection, tax-aware rebalancing, realized-gain reporting.

Lot-aware from day one: when ``portfolio_tax_lots`` rows exist for a
given (account, symbol), FIFO consumption math drives realized-gain
breakdown by holding period (long-term vs short-term). When no lot rows
exist (legacy positions backfilled by ``PortfolioManager``), the ledger
falls back to the position-level cost basis aggregate so callers never
crash on partial data.

All callers — internal agents, FastAPI routers, ``st`` — must import
this service and consume its dataclass contracts. Reimplementing this
math elsewhere is forbidden by the F1 SoT contract.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from ..logging_config import get_logger
from ..storage import PortfolioStorage

logger = get_logger(__name__)

TransactionType = Literal["buy", "sell", "dividend", "split"]

# IRS holding-period threshold: more than 1 year held qualifies for
# long-term capital gains treatment.
_LONG_TERM_DAYS = 365


@dataclass(slots=True, frozen=True)
class TransactionRow:
    """A single ledger row exactly as stored."""

    id: str
    account_id: str
    symbol: str
    transaction_type: TransactionType
    trade_date: date
    settlement_date: date | None
    shares: float
    price: float
    fees: float
    realized_gain: float | None
    source: str
    external_id: str | None
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(slots=True, frozen=True)
class TaxLot:
    """An open (or partially open) tax lot."""

    id: str
    account_id: str
    symbol: str
    acquired_date: date
    original_shares: float
    remaining_shares: float
    cost_per_share: float
    cost_basis_total: float
    acquisition_txn_id: str | None
    disposed_at: datetime | None


@dataclass(slots=True, frozen=True)
class LotConsumption:
    """How many shares were taken from a single lot during a sell."""

    lot_id: str | None
    acquired_date: date | None
    shares: float
    cost_basis: float
    proceeds: float
    realized_gain: float
    holding_period_days: int | None
    is_long_term: bool


@dataclass(slots=True, frozen=True)
class ConsumeResult:
    """Aggregate result of FIFO-consuming lots for a sell."""

    consumed: list[LotConsumption]
    total_shares: float
    total_cost_basis: float
    total_proceeds: float
    realized_gain_long_term: float
    realized_gain_short_term: float
    used_position_aggregate_fallback: bool

    @property
    def total_realized_gain(self) -> float:
        return self.realized_gain_long_term + self.realized_gain_short_term


class TransactionLedger:
    """Append-only buy/sell ledger backed by ``portfolio_transactions``.

    Methods are read-mostly and idempotent on ``external_id``. Lot
    bookkeeping (``portfolio_tax_lots``) is updated by
    ``record_transaction`` for real ``buy`` and ``sell`` rows; rows with
    ``source='legacy_aggregate'`` deliberately skip lot creation.
    """

    def __init__(self, storage: PortfolioStorage) -> None:
        self.storage = storage

    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------

    def record_transaction(
        self,
        *,
        account_id: str,
        symbol: str,
        transaction_type: TransactionType,
        trade_date: date,
        shares: float,
        price: float,
        fees: float = 0.0,
        settlement_date: date | None = None,
        source: str = "manual",
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Insert one transaction row, returning its UUID.

        Idempotent on ``(account_id, external_id)`` when ``external_id``
        is supplied: a duplicate import returns the existing row's id
        instead of inserting a second copy.

        For ``buy`` rows with ``source != 'legacy_aggregate'`` a matching
        open lot is created. For ``sell`` rows with the same constraint,
        FIFO consumption decrements existing lots and stamps
        ``realized_gain``. Legacy aggregate rows skip lot bookkeeping.
        """
        symbol_upper = symbol.upper()
        meta_payload = json.dumps(metadata or {})

        if external_id is not None:
            existing = self._find_by_external_id(account_id, external_id)
            if existing is not None:
                return existing

        txn_id = str(uuid.uuid4())
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_transactions
                    (id, account_id, symbol, transaction_type, trade_date,
                     settlement_date, shares, price, fees, source,
                     external_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                [
                    txn_id,
                    account_id,
                    symbol_upper,
                    transaction_type,
                    trade_date,
                    settlement_date,
                    shares,
                    price,
                    fees,
                    source,
                    external_id,
                    meta_payload,
                ],
            )
            conn.commit()

        if source == "legacy_aggregate":
            logger.debug(
                "legacy_aggregate_txn_recorded",
                txn_id=txn_id,
                account_id=account_id,
                symbol=symbol_upper,
            )
            return txn_id

        if transaction_type == "buy":
            self._open_lot_for_buy(
                txn_id=txn_id,
                account_id=account_id,
                symbol=symbol_upper,
                trade_date=trade_date,
                shares=shares,
                price=price,
                fees=fees,
            )
        elif transaction_type == "sell":
            consume = self.consume_lots_fifo(
                account_id=account_id,
                symbol=symbol_upper,
                shares=shares,
                sell_date=trade_date,
                sell_price=price,
            )
            self._stamp_realized_gain(txn_id, consume.total_realized_gain)

        return txn_id

    # ------------------------------------------------------------------
    # window queries
    # ------------------------------------------------------------------

    def recent_buys(
        self,
        account_ids: list[str],
        symbol: str,
        since_date: date,
        until_date: date | None = None,
    ) -> list[TransactionRow]:
        """Return all ``buy`` rows for ``symbol`` within an inclusive window.

        Used by the wash-sale detector, which must scan every household
        account (including spouse and tax-advantaged accounts per
        IRS Pub 550) for replacement purchases inside the 30-day window.
        """
        return self._window_query(account_ids, symbol, "buy", since_date, until_date)

    def recent_sells(
        self,
        account_ids: list[str],
        symbol: str,
        since_date: date,
        until_date: date | None = None,
    ) -> list[TransactionRow]:
        return self._window_query(account_ids, symbol, "sell", since_date, until_date)

    def realized_gains_ytd(self, account_id: str, year: int) -> dict[str, float]:
        """Return realized-gain totals for one account in one calendar year.

        Buckets by holding period: ``{'long_term': X, 'short_term': Y,
        'total': X+Y}``. Uses lot consumption history when present, else
        falls back to the ``realized_gain`` column on the sell row,
        treating it as short-term (worst-case) when holding period is
        unknown.
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        long_term = 0.0
        short_term = 0.0

        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, trade_date, realized_gain
                FROM portfolio_transactions
                WHERE account_id = %s
                  AND transaction_type = 'sell'
                  AND trade_date BETWEEN %s AND %s
                """,
                [account_id, start, end],
            ).fetchall()

        for txn_id, _trade_date, gain in rows:
            if gain is None:
                continue
            gain_value = float(gain)
            if gain_value == 0.0:
                continue
            split = self._lookup_holding_period_split(txn_id)
            if split is None:
                short_term += gain_value
            else:
                long_term += split.realized_gain_long_term
                short_term += split.realized_gain_short_term
                # split totals may not match aggregate when partial; trust split.

        total = long_term + short_term
        return {
            "long_term": round(long_term, 4),
            "short_term": round(short_term, 4),
            "total": round(total, 4),
        }

    # ------------------------------------------------------------------
    # lot reads
    # ------------------------------------------------------------------

    def open_lots(self, account_id: str, symbol: str) -> list[TaxLot]:
        """Return open lots (remaining_shares > 0) ordered FIFO.

        Empty list when no lot rows exist — callers that need cost-basis
        info should fall back to ``portfolio_positions.cost_basis``.
        """
        symbol_upper = symbol.upper()
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, account_id, symbol, acquired_date,
                       original_shares, remaining_shares, cost_per_share,
                       cost_basis_total, acquisition_txn_id, disposed_at
                FROM portfolio_tax_lots
                WHERE account_id = %s
                  AND symbol = %s
                  AND remaining_shares > 0
                ORDER BY acquired_date ASC, id ASC
                """,
                [account_id, symbol_upper],
            ).fetchall()

        return [
            TaxLot(
                id=str(row[0]),
                account_id=str(row[1]),
                symbol=str(row[2]),
                acquired_date=_to_date(row[3]),
                original_shares=float(row[4]),
                remaining_shares=float(row[5]),
                cost_per_share=float(row[6]),
                cost_basis_total=float(row[7]),
                acquisition_txn_id=str(row[8]) if row[8] is not None else None,
                disposed_at=_to_datetime(row[9]),
            )
            for row in rows
        ]

    def preview_lots_fifo(
        self,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        sell_date: date,
        sell_price: float,
    ) -> ConsumeResult:
        """Estimate FIFO lot consumption without changing stored tax lots.

        The returned gain and holding-period breakdown matches
        :meth:`consume_lots_fifo`, but repeated previews are idempotent. Use
        this path for rebalance proposals and other what-if flows.
        """
        return self._evaluate_lots_fifo(
            account_id=account_id,
            symbol=symbol,
            shares=shares,
            sell_date=sell_date,
            sell_price=sell_price,
            apply_updates=False,
        )

    def consume_lots_fifo(
        self,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        sell_date: date,
        sell_price: float,
    ) -> ConsumeResult:
        """FIFO-consume open lots for a sale that actually happened."""
        return self._evaluate_lots_fifo(
            account_id=account_id,
            symbol=symbol,
            shares=shares,
            sell_date=sell_date,
            sell_price=sell_price,
            apply_updates=True,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _evaluate_lots_fifo(
        self,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        sell_date: date,
        sell_price: float,
        apply_updates: bool,
    ) -> ConsumeResult:
        """Build a FIFO result and optionally persist the lot decrements."""
        symbol_upper = symbol.upper()
        lots = self.open_lots(account_id, symbol_upper)

        if not lots:
            return self._consume_via_position_aggregate(
                account_id=account_id,
                symbol=symbol_upper,
                shares=shares,
                sell_date=sell_date,
                sell_price=sell_price,
            )

        remaining_to_sell = shares
        consumed: list[LotConsumption] = []
        long_term_gain = 0.0
        short_term_gain = 0.0
        long_term_threshold = sell_date - timedelta(days=_LONG_TERM_DAYS)

        updates: list[tuple[str, float]] = []
        for lot in lots:
            if remaining_to_sell <= 0:
                break
            take = min(remaining_to_sell, lot.remaining_shares)
            if take <= 0:
                continue
            cost_basis = take * lot.cost_per_share
            proceeds = take * sell_price
            gain = proceeds - cost_basis
            holding_period = (sell_date - lot.acquired_date).days
            # IRS rule: held *more* than one year qualifies as
            # long-term. Acquired at or after one-year-prior is
            # short-term.
            is_long_term = lot.acquired_date < long_term_threshold

            consumed.append(
                LotConsumption(
                    lot_id=lot.id,
                    acquired_date=lot.acquired_date,
                    shares=take,
                    cost_basis=cost_basis,
                    proceeds=proceeds,
                    realized_gain=gain,
                    holding_period_days=holding_period,
                    is_long_term=is_long_term,
                )
            )
            if is_long_term:
                long_term_gain += gain
            else:
                short_term_gain += gain

            new_remaining = lot.remaining_shares - take
            updates.append((lot.id, new_remaining))
            remaining_to_sell -= take

        if apply_updates and updates:
            with self.storage.connection() as conn:
                for lot_id, new_remaining in updates:
                    disposed_at = datetime.now(UTC) if new_remaining <= 0 else None
                    conn.execute(
                        """
                        UPDATE portfolio_tax_lots
                        SET remaining_shares = %s,
                            disposed_at = COALESCE(%s, disposed_at),
                            updated_at = now()
                        WHERE id = %s
                        """,
                        [new_remaining, disposed_at, lot_id],
                    )
                conn.commit()

        # If we ran out of lots before filling the order, consume the
        # rest via the aggregate fallback. This happens when lots were
        # only partially backfilled.
        used_position_aggregate_fallback = remaining_to_sell > 0
        if used_position_aggregate_fallback:
            tail = self._consume_via_position_aggregate(
                account_id=account_id,
                symbol=symbol_upper,
                shares=remaining_to_sell,
                sell_date=sell_date,
                sell_price=sell_price,
            )
            consumed.extend(tail.consumed)
            long_term_gain += tail.realized_gain_long_term
            short_term_gain += tail.realized_gain_short_term

        total_shares = sum(c.shares for c in consumed)
        total_cost_basis = sum(c.cost_basis for c in consumed)
        total_proceeds = sum(c.proceeds for c in consumed)

        return ConsumeResult(
            consumed=consumed,
            total_shares=round(total_shares, 6),
            total_cost_basis=round(total_cost_basis, 4),
            total_proceeds=round(total_proceeds, 4),
            realized_gain_long_term=round(long_term_gain, 4),
            realized_gain_short_term=round(short_term_gain, 4),
            used_position_aggregate_fallback=used_position_aggregate_fallback,
        )

    def _find_by_external_id(self, account_id: str, external_id: str) -> str | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM portfolio_transactions
                WHERE account_id = %s AND external_id = %s
                LIMIT 1
                """,
                [account_id, external_id],
            ).fetchone()
        return str(row[0]) if row else None

    def _open_lot_for_buy(
        self,
        *,
        txn_id: str,
        account_id: str,
        symbol: str,
        trade_date: date,
        shares: float,
        price: float,
        fees: float,
    ) -> None:
        if shares <= 0:
            return
        # Allocate fees pro-rata into per-share basis so downstream FIFO
        # math reflects the true acquisition cost.
        cost_per_share = price + (fees / shares if shares else 0.0)
        cost_basis_total = cost_per_share * shares
        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_tax_lots
                    (id, account_id, symbol, acquired_date,
                     original_shares, remaining_shares, cost_per_share,
                     cost_basis_total, acquisition_txn_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    str(uuid.uuid4()),
                    account_id,
                    symbol,
                    trade_date,
                    shares,
                    shares,
                    cost_per_share,
                    cost_basis_total,
                    txn_id,
                ],
            )
            conn.commit()

    def _stamp_realized_gain(self, txn_id: str, realized_gain: float) -> None:
        with self.storage.connection() as conn:
            conn.execute(
                "UPDATE portfolio_transactions SET realized_gain = %s WHERE id = %s",
                [round(realized_gain, 4), txn_id],
            )
            conn.commit()

    def _window_query(
        self,
        account_ids: list[str],
        symbol: str,
        transaction_type: TransactionType,
        since_date: date,
        until_date: date | None,
    ) -> list[TransactionRow]:
        if not account_ids:
            return []
        until = until_date if until_date is not None else date.max
        symbol_upper = symbol.upper()
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, account_id, symbol, transaction_type, trade_date,
                       settlement_date, shares, price, fees, realized_gain,
                       source, external_id, metadata, created_at
                FROM portfolio_transactions
                WHERE account_id = ANY(%s)
                  AND symbol = %s
                  AND transaction_type = %s
                  AND trade_date BETWEEN %s AND %s
                ORDER BY trade_date ASC, created_at ASC
                """,
                [account_ids, symbol_upper, transaction_type, since_date, until],
            ).fetchall()
        return [_row_to_transaction(row) for row in rows]

    def _consume_via_position_aggregate(
        self,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        sell_date: date,
        sell_price: float,
    ) -> ConsumeResult:
        """Fallback when no lot rows exist for the (account, symbol).

        Reads ``portfolio_positions.cost_basis`` (per-share aggregate)
        and treats holding period as unknown — emits the gain as
        short-term, the conservative bucket for tax planning.
        """
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT cost_basis FROM portfolio_positions
                WHERE account_id = %s AND symbol = %s
                LIMIT 1
                """,
                [account_id, symbol],
            ).fetchone()

        cost_per_share = float(row[0]) if row and row[0] is not None else 0.0
        cost_basis = cost_per_share * shares
        proceeds = sell_price * shares
        gain = proceeds - cost_basis

        consumed = [
            LotConsumption(
                lot_id=None,
                acquired_date=None,
                shares=shares,
                cost_basis=cost_basis,
                proceeds=proceeds,
                realized_gain=gain,
                holding_period_days=None,
                is_long_term=False,
            )
        ]
        return ConsumeResult(
            consumed=consumed,
            total_shares=round(shares, 6),
            total_cost_basis=round(cost_basis, 4),
            total_proceeds=round(proceeds, 4),
            realized_gain_long_term=0.0,
            realized_gain_short_term=round(gain, 4),
            used_position_aggregate_fallback=True,
        )

    def _lookup_holding_period_split(self, sell_txn_id: str) -> ConsumeResult | None:
        """Reconstruct LT/ST split for a historical sell from disposed lots.

        Returns None when no lot history exists for the sell — callers
        should treat the gain as short-term (conservative).
        """
        # MVP: no per-sell consumption ledger yet. Return None so the
        # caller buckets gains as short-term. F2 may add a
        # ``portfolio_lot_consumptions`` table; this hook keeps the
        # contract stable when it does.
        _ = sell_txn_id
        return None


def _to_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Cannot coerce {value!r} to date")


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"Cannot coerce {value!r} to datetime")


def _row_to_transaction(row: tuple[Any, ...]) -> TransactionRow:
    metadata = row[12]
    if isinstance(metadata, str):
        metadata = json.loads(metadata) if metadata else {}
    elif metadata is None:
        metadata = {}

    return TransactionRow(
        id=str(row[0]),
        account_id=str(row[1]),
        symbol=str(row[2]),
        transaction_type=str(row[3]),
        trade_date=_to_date(row[4]),
        settlement_date=_to_date(row[5]) if row[5] is not None else None,
        shares=float(row[6]),
        price=float(row[7]),
        fees=float(row[8]),
        realized_gain=float(row[9]) if row[9] is not None else None,
        source=str(row[10]),
        external_id=str(row[11]) if row[11] is not None else None,
        metadata=dict(metadata),
        created_at=_to_datetime(row[13]) or datetime.now(UTC),
    )

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
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from ..storage.types import DatabaseConnection

logger = get_logger(__name__)

TransactionType = Literal["buy", "sell", "dividend", "split"]

# Storage precision of ``portfolio_tax_lots`` / ``portfolio_transactions``:
# shares and per-share prices are NUMERIC(18,6), money totals NUMERIC(18,4).
_SHARE_QUANT = Decimal("0.000001")
_PRICE_QUANT = Decimal("0.000001")
_MONEY_QUANT = Decimal("0.0001")
# Internal precision for pro-rata fee allocation before money rounding.
_ALLOCATION_QUANT = Decimal("0.0000000001")
_ZERO = Decimal(0)


def one_year_anniversary(acquired_date: date) -> date:
    """Return the first anniversary of an acquisition date.

    A Feb 29 acquisition has no same-day anniversary in a non-leap year; we
    map it to Feb 28 of the following year (the same convention as
    ``dateutil.relativedelta(years=1)``). Combined with the strict ``>``
    in :func:`is_long_term_holding`, a Feb 29, 2024 lot sold on Feb 28, 2025
    is short-term and one sold on Mar 1, 2025 is long-term.
    """
    try:
        return acquired_date.replace(year=acquired_date.year + 1)
    except ValueError:
        return date(acquired_date.year + 1, 2, 28)


def is_long_term_holding(acquired_date: date, disposed_date: date) -> bool:
    """IRS holding-period rule: long-term iff held *more than* one year.

    The holding period starts the day after acquisition, so a sale on the
    one-year anniversary is still short-term; the first long-term day is the
    day after the anniversary. Calendar-year based, so leap years are handled
    correctly (a fixed 365-day threshold is off by one across Feb 29).
    """
    return disposed_date > one_year_anniversary(acquired_date)


def _dec(value: Any) -> Decimal:
    """Convert a DB NUMERIC / float / int boundary value to ``Decimal``.

    Floats go through ``str`` so ``0.1`` becomes ``Decimal('0.1')`` rather
    than its binary expansion.
    """
    if isinstance(value, Decimal):
        return value
    if value is None:
        return _ZERO
    return Decimal(str(value))


def _shares_dec(value: Any) -> Decimal:
    return _dec(value).quantize(_SHARE_QUANT)


def _money_float(value: Decimal) -> float:
    return float(value.quantize(_MONEY_QUANT))


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
    # ``None`` when no basis source exists (no lot and no position
    # aggregate): the gain is unknown rather than fabricated from 0 basis.
    cost_basis: float | None
    # Net of the pro-rata share of sell fees.
    proceeds: float
    realized_gain: float | None
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
    # True when some consumed shares had no basis source at all. The LT/ST
    # buckets and ``total_cost_basis`` then cover only the known-basis
    # shares and ``total_realized_gain`` is ``None``.
    basis_unknown: bool = False
    unknown_basis_shares: float = 0.0

    @property
    def total_realized_gain(self) -> float | None:
        if self.basis_unknown:
            return None
        return round(self.realized_gain_long_term + self.realized_gain_short_term, 4)


@dataclass(slots=True)
class _LotState:
    """Mutable Decimal view of one lot used by FIFO math and replay."""

    id: str
    acquired_date: date
    remaining: Decimal
    cost_per_share: Decimal


@dataclass(slots=True, frozen=True)
class _Piece:
    """Shares taken from one basis source (a lot or the aggregate tail)."""

    lot_id: str | None
    acquired_date: date | None
    shares: Decimal
    cost_basis: Decimal | None


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

        txn_id = str(uuid.uuid4())
        with self.storage.connection() as conn:
            try:
                inserted = conn.execute(
                    """
                    INSERT INTO portfolio_transactions
                        (id, account_id, symbol, transaction_type, trade_date,
                         settlement_date, shares, price, fees, source,
                         external_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (account_id, external_id)
                        WHERE external_id IS NOT NULL
                    DO NOTHING
                    RETURNING id
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
                ).fetchone()

                if inserted is None:
                    if external_id is None:
                        raise RuntimeError("Transaction insert returned no id")
                    existing = self._find_by_external_id_with_connection(
                        conn, account_id, external_id
                    )
                    if existing is None:
                        raise RuntimeError(
                            "External-id conflict did not resolve to a transaction"
                        )
                    # The conflict path performed no writes. End its transaction
                    # before returning the already-committed canonical row.
                    conn.rollback()
                    return existing

                txn_id = str(inserted[0])

                lot_bookkeeping = source != "legacy_aggregate" and transaction_type in (
                    "buy",
                    "sell",
                )
                # A trade dated before an already-processed sell changes which
                # lots that sell should have consumed, so incremental FIFO is
                # no longer valid: replay the whole (account, symbol) history.
                out_of_order = lot_bookkeeping and self._has_later_sell(
                    conn,
                    account_id=account_id,
                    symbol=symbol_upper,
                    trade_date=trade_date,
                )

                if source != "legacy_aggregate" and transaction_type == "buy":
                    self._open_lot_for_buy(
                        conn,
                        txn_id=txn_id,
                        account_id=account_id,
                        symbol=symbol_upper,
                        trade_date=trade_date,
                        shares=shares,
                        price=price,
                        fees=fees,
                    )
                elif (
                    source != "legacy_aggregate"
                    and transaction_type == "sell"
                    and not out_of_order
                ):
                    consume = self._evaluate_lots_fifo(
                        account_id=account_id,
                        symbol=symbol_upper,
                        shares=shares,
                        sell_date=trade_date,
                        sell_price=price,
                        fees=fees,
                        apply_updates=True,
                        connection=conn,
                    )
                    self._stamp_realized_gain(conn, txn_id, consume.total_realized_gain)

                if out_of_order:
                    self._replay_lots_and_gains(
                        conn, account_id=account_id, symbol=symbol_upper
                    )

                conn.commit()
            except Exception:
                conn.rollback()
                raise

        if source == "legacy_aggregate":
            logger.debug(
                "legacy_aggregate_txn_recorded",
                txn_id=txn_id,
                account_id=account_id,
                symbol=symbol_upper,
            )

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
        'total': X+Y, 'unknown_gain_sells': N}``. Uses lot consumption
        history when present, else falls back to the ``realized_gain``
        column on the sell row, treating it as short-term (worst-case) when
        holding period is unknown.

        Sells whose ``realized_gain`` is NULL (no basis source, or legacy
        aggregate rows that never stamp a gain) are excluded from the money
        totals and counted in ``unknown_gain_sells`` so callers can tell the
        totals are incomplete instead of reading them as zero gain.
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        long_term = 0.0
        short_term = 0.0
        unknown_gain_sells = 0

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
                unknown_gain_sells += 1
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
            "unknown_gain_sells": unknown_gain_sells,
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
            return self._open_lots_with_connection(
                conn, account_id=account_id, symbol=symbol_upper, for_update=False
            )

    def preview_lots_fifo(
        self,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        sell_date: date,
        sell_price: float,
        fees: float = 0.0,
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
            fees=fees,
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
        fees: float = 0.0,
    ) -> ConsumeResult:
        """FIFO-consume open lots for a sale that actually happened."""
        return self._evaluate_lots_fifo(
            account_id=account_id,
            symbol=symbol,
            shares=shares,
            sell_date=sell_date,
            sell_price=sell_price,
            fees=fees,
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
        fees: float = 0.0,
        connection: DatabaseConnection | None = None,
    ) -> ConsumeResult:
        """Build a FIFO result and optionally persist the lot decrements.

        Mutating callers either supply their surrounding transaction or let
        this method own one. Preview callers never request row locks or commit.
        ``fees`` are sell-side costs; they reduce proceeds pro-rata by shares
        across every consumed lot (what-if previews legitimately pass 0).
        """
        if connection is not None:
            return self._evaluate_lots_fifo_with_connection(
                connection,
                account_id=account_id,
                symbol=symbol,
                shares=shares,
                sell_date=sell_date,
                sell_price=sell_price,
                fees=fees,
                apply_updates=apply_updates,
            )

        with self.storage.connection() as conn:
            try:
                result = self._evaluate_lots_fifo_with_connection(
                    conn,
                    account_id=account_id,
                    symbol=symbol,
                    shares=shares,
                    sell_date=sell_date,
                    sell_price=sell_price,
                    fees=fees,
                    apply_updates=apply_updates,
                )
                if apply_updates:
                    conn.commit()
                return result
            except Exception:
                if apply_updates:
                    conn.rollback()
                raise

    def _evaluate_lots_fifo_with_connection(
        self,
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
        shares: float,
        sell_date: date,
        sell_price: float,
        fees: float,
        apply_updates: bool,
    ) -> ConsumeResult:
        """Evaluate FIFO using one connection, locking rows before mutation.

        All share/basis/gain arithmetic is ``Decimal`` so NUMERIC values do
        not pick up float residue (e.g. a ``1e-16`` share remainder that
        would wrongly trigger the aggregate fallback).
        """
        symbol_upper = symbol.upper()
        lots = self._lot_states_with_connection(
            connection,
            account_id=account_id,
            symbol=symbol_upper,
            for_update=apply_updates,
        )

        pieces, unfilled = _fifo_take(lots, _shares_dec(shares))

        if apply_updates:
            for piece in pieces:
                lot = next(state for state in lots if state.id == piece.lot_id)
                disposed_at = datetime.now(UTC) if lot.remaining <= 0 else None
                connection.execute(
                    """
                    UPDATE portfolio_tax_lots
                    SET remaining_shares = %s,
                        disposed_at = COALESCE(%s, disposed_at),
                        updated_at = now()
                    WHERE id = %s
                    """,
                    [lot.remaining, disposed_at, lot.id],
                )

        # If we ran out of lots before filling the order, consume the
        # rest via the aggregate fallback. This happens when lots were
        # only partially backfilled (or never existed).
        used_position_aggregate_fallback = unfilled > 0
        if used_position_aggregate_fallback:
            pieces.append(
                self._aggregate_tail_piece(
                    connection,
                    account_id=account_id,
                    symbol=symbol_upper,
                    shares=unfilled,
                )
            )

        result = _build_consume_result(
            pieces,
            sell_date=sell_date,
            sell_price=_dec(sell_price),
            fees=_dec(fees),
            used_position_aggregate_fallback=used_position_aggregate_fallback,
        )
        if result.basis_unknown:
            logger.warning(
                "realized_gain_basis_unknown",
                account_id=account_id,
                symbol=symbol_upper,
                sell_date=sell_date.isoformat(),
                unknown_basis_shares=result.unknown_basis_shares,
                apply_updates=apply_updates,
            )
        return result

    def _has_later_sell(
        self,
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
        trade_date: date,
    ) -> bool:
        """True when a lot-tracked sell for (account, symbol) is dated later."""
        row = connection.execute(
            """
            SELECT 1 FROM portfolio_transactions
            WHERE account_id = %s
              AND symbol = %s
              AND transaction_type = 'sell'
              AND source <> 'legacy_aggregate'
              AND trade_date > %s
            LIMIT 1
            """,
            [account_id, symbol, trade_date],
        ).fetchone()
        return row is not None

    def _replay_lots_and_gains(
        self,
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
    ) -> None:
        """Rebuild lot remainders and sell gains from ordered history.

        Runs inside the caller's transaction. Every lot for the
        (account, symbol) is reset to its ``original_shares`` and every
        lot-tracked sell is re-applied in ``(trade_date, created_at, id)``
        order. A sell only consumes lots acquired on or before its trade
        date. Each sell's ``realized_gain`` is re-stamped (NULL when basis is
        unknown) and each lot's ``remaining_shares`` / ``disposed_at`` is
        rewritten; a lot that is no longer fully consumed is reopened.
        """
        lot_rows = connection.execute(
            """
            SELECT id, acquired_date, original_shares, cost_per_share, disposed_at
            FROM portfolio_tax_lots
            WHERE account_id = %s AND symbol = %s
            ORDER BY acquired_date ASC, id ASC
            FOR UPDATE
            """,
            [account_id, symbol],
        ).fetchall()
        lots = [
            _LotState(
                id=str(row[0]),
                acquired_date=_to_date(row[1]),
                remaining=_shares_dec(row[2]),
                cost_per_share=_dec(row[3]),
            )
            for row in lot_rows
        ]
        prior_disposed = {str(row[0]): _to_datetime(row[4]) for row in lot_rows}

        sells = connection.execute(
            """
            SELECT id, trade_date, shares, price, fees
            FROM portfolio_transactions
            WHERE account_id = %s
              AND symbol = %s
              AND transaction_type = 'sell'
              AND source <> 'legacy_aggregate'
            ORDER BY trade_date ASC, created_at ASC, id ASC
            """,
            [account_id, symbol],
        ).fetchall()

        for sell_id, raw_trade_date, raw_shares, raw_price, raw_fees in sells:
            sell_date = _to_date(raw_trade_date)
            eligible = [lot for lot in lots if lot.acquired_date <= sell_date]
            pieces, unfilled = _fifo_take(eligible, _shares_dec(raw_shares))
            used_fallback = unfilled > 0
            if used_fallback:
                pieces.append(
                    self._aggregate_tail_piece(
                        connection, account_id=account_id, symbol=symbol, shares=unfilled
                    )
                )
            result = _build_consume_result(
                pieces,
                sell_date=sell_date,
                sell_price=_dec(raw_price),
                fees=_dec(raw_fees),
                used_position_aggregate_fallback=used_fallback,
            )
            if result.basis_unknown:
                logger.warning(
                    "realized_gain_basis_unknown",
                    account_id=account_id,
                    symbol=symbol,
                    sell_date=sell_date.isoformat(),
                    unknown_basis_shares=result.unknown_basis_shares,
                    apply_updates=True,
                )
            self._stamp_realized_gain(connection, str(sell_id), result.total_realized_gain)

        now = datetime.now(UTC)
        for lot in lots:
            disposed_at = (prior_disposed.get(lot.id) or now) if lot.remaining <= 0 else None
            connection.execute(
                """
                UPDATE portfolio_tax_lots
                SET remaining_shares = %s,
                    disposed_at = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                [lot.remaining, disposed_at, lot.id],
            )
        logger.info(
            "tax_lots_replayed",
            account_id=account_id,
            symbol=symbol,
            lots=len(lots),
            sells=len(sells),
        )

    def _lot_states_with_connection(
        self,
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
        for_update: bool,
    ) -> list[_LotState]:
        return [
            _LotState(
                id=str(row[0]),
                acquired_date=_to_date(row[3]),
                remaining=_shares_dec(row[5]),
                cost_per_share=_dec(row[6]),
            )
            for row in self._open_lot_rows(
                connection, account_id=account_id, symbol=symbol, for_update=for_update
            )
        ]

    @staticmethod
    def _open_lot_rows(
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
        for_update: bool,
    ) -> list[tuple[Any, ...]]:
        lock_clause = " FOR UPDATE" if for_update else ""
        return list(
            connection.execute(
                f"""
                SELECT id, account_id, symbol, acquired_date,
                       original_shares, remaining_shares, cost_per_share,
                       cost_basis_total, acquisition_txn_id, disposed_at
                FROM portfolio_tax_lots
                WHERE account_id = %s
                  AND symbol = %s
                  AND remaining_shares > 0
                ORDER BY acquired_date ASC, id ASC{lock_clause}
                """,
                [account_id, symbol],
            ).fetchall()
        )

    def _open_lots_with_connection(
        self,
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
        for_update: bool,
    ) -> list[TaxLot]:
        rows = self._open_lot_rows(
            connection, account_id=account_id, symbol=symbol, for_update=for_update
        )
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

    def _find_by_external_id(self, account_id: str, external_id: str) -> str | None:
        with self.storage.connection() as conn:
            return self._find_by_external_id_with_connection(conn, account_id, external_id)

    @staticmethod
    def _find_by_external_id_with_connection(
        connection: DatabaseConnection, account_id: str, external_id: str
    ) -> str | None:
        row = connection.execute(
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
        connection: DatabaseConnection,
        *,
        txn_id: str,
        account_id: str,
        symbol: str,
        trade_date: date,
        shares: float,
        price: float,
        fees: float,
    ) -> None:
        shares_dec = _shares_dec(shares)
        if shares_dec <= 0:
            return
        # Allocate fees pro-rata into per-share basis so downstream FIFO
        # math reflects the true acquisition cost.
        cost_basis_total = _dec(price) * shares_dec + _dec(fees)
        cost_per_share = (cost_basis_total / shares_dec).quantize(_PRICE_QUANT)
        connection.execute(
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
                shares_dec,
                shares_dec,
                cost_per_share,
                cost_basis_total.quantize(_MONEY_QUANT),
                txn_id,
            ],
        )

    @staticmethod
    def _stamp_realized_gain(
        connection: DatabaseConnection, txn_id: str, realized_gain: float | None
    ) -> None:
        """Persist a sell's realized gain; ``None`` stores NULL (basis unknown)."""
        value = None if realized_gain is None else _dec(realized_gain).quantize(_MONEY_QUANT)
        connection.execute(
            "UPDATE portfolio_transactions SET realized_gain = %s WHERE id = %s",
            [value, txn_id],
        )

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

    @staticmethod
    def _aggregate_tail_piece(
        connection: DatabaseConnection,
        *,
        account_id: str,
        symbol: str,
        shares: Decimal,
    ) -> _Piece:
        """Fallback basis for shares not covered by lot rows.

        Reads ``portfolio_positions.cost_basis`` (per-share aggregate) and
        treats holding period as unknown, so the gain lands in the
        short-term bucket (conservative for tax planning). When no position
        row / cost basis exists, the basis is ``None``: the gain is unknown
        and is never fabricated from a zero basis.
        """
        row = connection.execute(
            """
            SELECT cost_basis FROM portfolio_positions
            WHERE account_id = %s AND symbol = %s
            LIMIT 1
            """,
            [account_id, symbol],
        ).fetchone()
        cost_basis = None if row is None or row[0] is None else _dec(row[0]) * shares
        return _Piece(lot_id=None, acquired_date=None, shares=shares, cost_basis=cost_basis)

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


def _fifo_take(lots: list[_LotState], shares: Decimal) -> tuple[list[_Piece], Decimal]:
    """Take ``shares`` FIFO from ``lots`` (already ordered), mutating remainders.

    Returns the pieces taken and the unfilled share count (exactly zero when
    the lots covered the order, thanks to Decimal arithmetic).
    """
    remaining_to_sell = shares
    pieces: list[_Piece] = []
    for lot in lots:
        if remaining_to_sell <= 0:
            break
        take = min(remaining_to_sell, lot.remaining)
        if take <= 0:
            continue
        pieces.append(
            _Piece(
                lot_id=lot.id,
                acquired_date=lot.acquired_date,
                shares=take,
                cost_basis=take * lot.cost_per_share,
            )
        )
        lot.remaining -= take
        remaining_to_sell -= take
    return pieces, max(remaining_to_sell, _ZERO)


def _build_consume_result(
    pieces: list[_Piece],
    *,
    sell_date: date,
    sell_price: Decimal,
    fees: Decimal,
    used_position_aggregate_fallback: bool,
) -> ConsumeResult:
    """Price the consumed pieces: allocate sell fees, bucket LT/ST gains.

    Sell fees reduce proceeds pro-rata by shares across all pieces; the last
    piece absorbs the rounding remainder so allocated fees sum exactly to
    ``fees``.
    """
    total_shares = sum((piece.shares for piece in pieces), _ZERO)
    fees_left = fees
    consumed: list[LotConsumption] = []
    long_term_gain = _ZERO
    short_term_gain = _ZERO
    known_cost_basis = _ZERO
    total_proceeds = _ZERO
    unknown_shares = _ZERO

    for index, piece in enumerate(pieces):
        if index == len(pieces) - 1:
            fee = fees_left
        else:
            fee = (fees * piece.shares / total_shares).quantize(_ALLOCATION_QUANT)
            fees_left -= fee
        proceeds = piece.shares * sell_price - fee
        total_proceeds += proceeds

        if piece.acquired_date is not None:
            holding_period: int | None = (sell_date - piece.acquired_date).days
            is_long_term = is_long_term_holding(piece.acquired_date, sell_date)
        else:
            holding_period = None
            is_long_term = False

        gain: Decimal | None
        if piece.cost_basis is None:
            gain = None
            unknown_shares += piece.shares
        else:
            gain = proceeds - piece.cost_basis
            known_cost_basis += piece.cost_basis
            if is_long_term:
                long_term_gain += gain
            else:
                short_term_gain += gain

        consumed.append(
            LotConsumption(
                lot_id=piece.lot_id,
                acquired_date=piece.acquired_date,
                shares=float(piece.shares),
                cost_basis=None if piece.cost_basis is None else _money_float(piece.cost_basis),
                proceeds=_money_float(proceeds),
                realized_gain=None if gain is None else _money_float(gain),
                holding_period_days=holding_period,
                is_long_term=is_long_term,
            )
        )

    return ConsumeResult(
        consumed=consumed,
        total_shares=float(total_shares.quantize(_SHARE_QUANT)),
        total_cost_basis=_money_float(known_cost_basis),
        total_proceeds=_money_float(total_proceeds),
        realized_gain_long_term=_money_float(long_term_gain),
        realized_gain_short_term=_money_float(short_term_gain),
        used_position_aggregate_fallback=used_position_aggregate_fallback,
        basis_unknown=unknown_shares > 0,
        unknown_basis_shares=float(unknown_shares),
    )


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

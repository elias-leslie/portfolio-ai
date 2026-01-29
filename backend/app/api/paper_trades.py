"""Paper Trading API endpoints.

This module provides REST API endpoints for paper trading operations:
- List all paper trades (open + closed)
- Get single trade details with AI reasoning
- Close positions manually
- Get summary statistics
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Literal, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.analytics.cash_manager import CashManager
from app.logging_config import get_logger
from app.storage import get_storage

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

router = APIRouter(prefix="/api/paper-trades", tags=["paper-trades"])

storage = get_storage()

# ============================================================================
# Request/Response Models
# ============================================================================


class PaperTradeResponse(BaseModel):
    """Response model for a single paper trade."""

    idea_id: str
    agent_run_id: str
    symbol: str
    idea_type: Literal["buy", "sell"]
    shares: int | None = None
    entry_price: float | None = None
    entry_amount: float | None = None
    entry_date: str | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    current_price: float | None = None
    current_return_pct: float | None = None
    status: str
    exit_price: float | None = None
    exit_date: str | None = None
    exit_reason: str | None = None
    realized_return_pct: float | None = None
    holding_days: int | None = None
    max_favorable_pct: float | None = None
    max_adverse_pct: float | None = None
    # AI reasoning fields
    thesis: str | None = None
    confidence_score: float | None = None
    risk_level: str | None = None
    # Agent approval details
    workflow_id: str | None = None
    strategy_agent_approved: bool | None = None
    risk_agent_approved: bool | None = None
    backtest_sharpe: float | None = None
    backtest_win_rate: float | None = None
    backtest_max_drawdown: float | None = None
    # Strategy linkage
    strategy_id: str | None = None


class PaperTradesListResponse(BaseModel):
    """Response model for list of paper trades."""

    trades: list[PaperTradeResponse]
    total_count: int


class PaperTradeSummaryResponse(BaseModel):
    """Response model for paper trading summary statistics."""

    total_open: int
    total_closed: int
    win_rate: float
    avg_return_pct: float
    total_pnl_pct: float
    best_trade_pct: float | None = None
    worst_trade_pct: float | None = None
    # Paper trading account balances
    cash_balance: float | None = None
    starting_balance: float | None = None
    positions_value: float | None = None
    total_portfolio_value: float | None = None


class CloseTradeRequest(BaseModel):
    """Request model for manually closing a paper trade."""

    exit_price: float | None = Field(
        None, description="Optional exit price (uses current if not provided)"
    )
    exit_reason: str = Field(default="manual", description="Reason for closing (default: manual)")


class CloseTradeResponse(BaseModel):
    """Response model for close trade operation."""

    status: str
    trade_id: str
    symbol: str
    exit_price: float
    exit_date: str
    realized_return_pct: float
    message: str


class ResetAccountRequest(BaseModel):
    """Request model for resetting paper trading account."""

    new_starting_balance: float | None = Field(
        None, description="New starting balance (uses current initial_cash if not provided)"
    )
    close_open_trades: bool = Field(
        default=True, description="Whether to close all open trades before reset"
    )


class ResetAccountResponse(BaseModel):
    """Response model for reset account operation."""

    status: str
    previous_balance: float
    new_balance: float
    trades_closed: int
    message: str


class UpdateSettingsRequest(BaseModel):
    """Request model for updating paper trading settings."""

    starting_balance: float = Field(..., gt=0, description="New starting balance amount")


class UpdateSettingsResponse(BaseModel):
    """Response model for update settings operation."""

    status: str
    starting_balance: float
    cash_balance: float
    message: str


# ============================================================================
# Helper Functions
# ============================================================================


def _row_to_paper_trade_response(row: tuple[object, ...]) -> PaperTradeResponse:
    """Convert database row tuple to PaperTradeResponse model.

    Column indices:
        0=idea_id, 1=agent_run_id, 2=symbol, 3=idea_type, 4=shares,
        5=entry_price, 6=entry_amount, 7=entry_date, 8=target_price,
        9=stop_loss_price, 10=current_price, 11=current_return_pct,
        12=status, 13=exit_price, 14=exit_date, 15=exit_reason,
        16=realized_return_pct, 17=holding_days, 18=max_favorable_pct,
        19=max_adverse_pct, 20=thesis, 21=confidence_score, 22=risk_level,
        23=strategy_id

    Args:
        row: Tuple from database query

    Returns:
        PaperTradeResponse model instance
    """
    return PaperTradeResponse(
        idea_id=str(row[0]) if row[0] else "",
        agent_run_id=str(row[1]) if row[1] else "",
        symbol=str(row[2]) if row[2] else "",
        idea_type=str(row[3]) if row[3] in ["buy", "sell"] else "buy",  # type: ignore[arg-type]
        shares=int(cast(int, row[4])) if row[4] is not None else None,
        entry_price=float(cast(float, row[5])) if row[5] is not None else None,
        entry_amount=float(cast(float, row[6])) if row[6] is not None else None,
        entry_date=str(row[7]) if row[7] else None,
        target_price=float(cast(float, row[8])) if row[8] is not None else None,
        stop_loss_price=float(cast(float, row[9])) if row[9] is not None else None,
        current_price=float(cast(float, row[10])) if row[10] is not None else None,
        current_return_pct=float(cast(float, row[11])) if row[11] is not None else None,
        status=str(row[12]) if row[12] else "",
        exit_price=float(cast(float, row[13])) if row[13] is not None else None,
        exit_date=str(row[14]) if row[14] else None,
        exit_reason=str(row[15]) if row[15] else None,
        realized_return_pct=float(cast(float, row[16])) if row[16] is not None else None,
        holding_days=int(cast(int, row[17])) if row[17] is not None else None,
        max_favorable_pct=float(cast(float, row[18])) if row[18] is not None else None,
        max_adverse_pct=float(cast(float, row[19])) if row[19] is not None else None,
        thesis=str(row[20]) if row[20] else None,
        confidence_score=float(cast(float, row[21])) if row[21] is not None else None,
        risk_level=str(row[22]) if row[22] else None,
        strategy_id=str(row[23]) if row[23] else None,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", response_model=PaperTradesListResponse)
async def list_paper_trades(
    status: Literal["open", "closed", "all"] = Query("all", description="Filter by trade status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of trades to return"),
    offset: int = Query(0, ge=0, description="Number of trades to skip"),
) -> PaperTradesListResponse:
    """List all paper trades with optional status filter.

    Query Parameters:
        status: Filter by 'open', 'closed', or 'all' (default: all)
        limit: Maximum number of trades to return (default: 100, max: 500)
        offset: Number of trades to skip for pagination (default: 0)

    Returns:
        List of paper trades with full details including AI reasoning
    """
    try:
        # Build query with status filter
        status_filter = ""
        params: list[int] = [limit, offset]

        if status == "open":
            status_filter = "WHERE io.status = 'open'"
        elif status == "closed":
            status_filter = "WHERE io.status IN ('closed', 'target_hit', 'stop_hit', 'expired')"

        # For open trades: use live price from price_cache and calculate P&L dynamically
        # For closed trades: use stored exit prices
        query = f"""
            WITH latest_prices AS (
                SELECT DISTINCT ON (symbol)
                    symbol,
                    price
                FROM price_cache
                WHERE cached_at >= NOW() - INTERVAL '1 hour'
                ORDER BY symbol, cached_at DESC
            )
            SELECT
                io.idea_id,
                io.agent_run_id,
                io.symbol,
                io.idea_type,
                io.shares,
                io.entry_price,
                io.entry_amount,
                io.entry_date,
                io.target_price,
                io.stop_loss_price,
                -- For open trades: use live price from cache, fallback to stored
                CASE
                    WHEN io.status = 'open' THEN COALESCE(lp.price, io.current_price)
                    ELSE io.current_price
                END as current_price,
                -- For open trades: calculate P&L dynamically from live price
                CASE
                    WHEN io.status = 'open' AND io.entry_price > 0 THEN
                        CASE
                            WHEN io.idea_type = 'sell' THEN
                                ((io.entry_price - COALESCE(lp.price, io.current_price)) / io.entry_price) * 100
                            ELSE
                                ((COALESCE(lp.price, io.current_price) - io.entry_price) / io.entry_price) * 100
                        END
                    ELSE io.current_return_pct
                END as current_return_pct,
                io.status,
                io.exit_price,
                io.exit_date,
                io.exit_reason,
                io.realized_return_pct,
                CASE
                    WHEN io.status = 'open' AND io.entry_date IS NOT NULL
                    THEN CURRENT_DATE - io.entry_date::date
                    ELSE io.holding_days
                END as holding_days,
                io.max_favorable_pct,
                io.max_adverse_pct,
                NULL as thesis,
                NULL as confidence_score,
                NULL as risk_level,
                io.strategy_id
            FROM idea_outcomes io
            LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
            {status_filter}
            ORDER BY
                CASE WHEN io.status = 'open' THEN 0 ELSE 1 END,
                io.entry_date DESC
            LIMIT ? OFFSET ?
        """

        with storage.connection() as conn:
            rows = conn.execute(query, tuple(params) if params else None).fetchall()

            # Get total count
            count_query = f"""
                SELECT COUNT(*) FROM idea_outcomes io
                {status_filter}
            """
            total_count = conn.execute(count_query).fetchone()[0]  # type: ignore[index]

        # Convert to response models using shared helper
        trades = [_row_to_paper_trade_response(row) for row in rows]

        logger.info(
            "paper_trades_listed",
            status_filter=status,
            count=len(trades),
            total=total_count,
        )

        return PaperTradesListResponse(
            trades=trades, total_count=int(total_count) if total_count else 0
        )

    except Exception as e:
        logger.error("failed_to_list_paper_trades", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch paper trades: {e}",
        ) from e


@router.get("/summary", response_model=PaperTradeSummaryResponse)
async def get_paper_trade_summary() -> PaperTradeSummaryResponse:
    """Get summary statistics for paper trading performance.

    Returns:
        Summary with win rate, average return, total P&L, etc.
    """
    try:
        with storage.connection() as conn:
            # Get counts
            open_count = conn.execute(
                "SELECT COUNT(*) FROM idea_outcomes WHERE status = 'open'"
            ).fetchone()[0]  # type: ignore[index]

            closed_count = conn.execute(
                "SELECT COUNT(*) FROM idea_outcomes WHERE status IN ('closed', 'target_hit', 'stop_hit', 'expired')"
            ).fetchone()[0]  # type: ignore[index]

            # Get closed trade stats
            stats = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN realized_return_pct > 0 THEN 1 END) as wins,
                    AVG(realized_return_pct) as avg_return,
                    SUM(realized_return_pct) as total_return,
                    MAX(realized_return_pct) as best_trade,
                    MIN(realized_return_pct) as worst_trade
                FROM idea_outcomes
                WHERE status IN ('closed', 'target_hit', 'stop_hit', 'expired')
                    AND realized_return_pct IS NOT NULL
                """
            ).fetchone()

            total_closed_with_returns = int(stats[0]) if stats[0] else 0  # type: ignore[index]
            wins = int(stats[1]) if stats[1] else 0  # type: ignore[index]
            avg_return = float(stats[2]) if stats[2] else 0.0  # type: ignore[index]
            float(stats[3]) if stats[3] else 0.0  # type: ignore[index]
            best_trade = float(stats[4]) if stats[4] is not None else None  # type: ignore[index]
            worst_trade = float(stats[5]) if stats[5] is not None else None  # type: ignore[index]

            win_rate = (
                (float(wins) / float(total_closed_with_returns) * 100.0)
                if total_closed_with_returns > 0
                else 0.0
            )

            # Get paper trading account balances
            account_row = conn.execute(
                """
                SELECT cash_balance, initial_cash
                FROM portfolio_accounts
                WHERE id = 'paper_trading'
                """
            ).fetchone()

            # Type narrow: account_row[0] and account_row[1] are DB values (str | int | float | bool | None)
            cash_balance = (
                float(account_row[0]) if account_row and account_row[0] is not None else None
            )
            starting_balance = (
                float(account_row[1]) if account_row and account_row[1] is not None else None
            )

            # Calculate positions value from open trades using live prices from price_cache
            positions_value_row = conn.execute(
                """
                WITH latest_prices AS (
                    SELECT DISTINCT ON (symbol)
                        symbol,
                        price
                    FROM price_cache
                    WHERE cached_at >= NOW() - INTERVAL '1 hour'
                    ORDER BY symbol, cached_at DESC
                )
                SELECT COALESCE(SUM(
                    io.shares * COALESCE(lp.price, io.current_price, io.entry_price)
                ), 0)
                FROM idea_outcomes io
                LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
                WHERE io.status = 'open' AND io.shares IS NOT NULL
                """
            ).fetchone()
            # Type narrow: positions_value_row[0] is a DB value (str | int | float | bool | None)
            positions_value = (
                float(positions_value_row[0])
                if positions_value_row and positions_value_row[0] is not None
                else 0.0
            )

            # Total portfolio value
            total_portfolio_value = (
                (cash_balance or 0.0) + positions_value if cash_balance is not None else None
            )

        logger.info(
            "paper_trade_summary_retrieved",
            open=open_count,
            closed=closed_count,
            win_rate=win_rate,
            cash_balance=cash_balance,
        )

        # Calculate actual portfolio P&L percentage (not sum of individual trade %)
        actual_pnl_pct = 0.0
        if starting_balance and starting_balance > 0 and total_portfolio_value is not None:
            actual_pnl_pct = ((total_portfolio_value - starting_balance) / starting_balance) * 100

        return PaperTradeSummaryResponse(
            total_open=int(open_count) if open_count else 0,
            total_closed=int(closed_count) if closed_count else 0,
            win_rate=float(win_rate) if win_rate else 0.0,
            avg_return_pct=float(avg_return) if avg_return else 0.0,
            total_pnl_pct=actual_pnl_pct,
            best_trade_pct=float(best_trade) if best_trade is not None else None,
            worst_trade_pct=float(worst_trade) if worst_trade is not None else None,
            cash_balance=cash_balance,
            starting_balance=starting_balance,
            positions_value=positions_value,
            total_portfolio_value=total_portfolio_value,
        )

    except Exception as e:
        logger.error("failed_to_get_summary", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch summary: {e}",
        ) from e


@router.get("/{trade_id}", response_model=PaperTradeResponse)
async def get_paper_trade(trade_id: str) -> PaperTradeResponse:
    """Get detailed information for a single paper trade.

    Path Parameters:
        trade_id: The idea_id of the paper trade

    Returns:
        Complete trade details including AI reasoning and backtest metrics
    """
    try:
        # Use live prices from price_cache for open trades
        query = """
            WITH latest_prices AS (
                SELECT DISTINCT ON (symbol)
                    symbol,
                    price
                FROM price_cache
                WHERE cached_at >= NOW() - INTERVAL '1 hour'
                ORDER BY symbol, cached_at DESC
            )
            SELECT
                io.idea_id,
                io.agent_run_id,
                io.symbol,
                io.idea_type,
                io.entry_price,
                io.entry_date,
                io.target_price,
                io.stop_loss_price,
                -- For open trades: use live price from cache
                CASE
                    WHEN io.status = 'open' THEN COALESCE(lp.price, io.current_price)
                    ELSE io.current_price
                END as current_price,
                -- For open trades: calculate P&L dynamically
                CASE
                    WHEN io.status = 'open' AND io.entry_price > 0 THEN
                        CASE
                            WHEN io.idea_type = 'sell' THEN
                                ((io.entry_price - COALESCE(lp.price, io.current_price)) / io.entry_price) * 100
                            ELSE
                                ((COALESCE(lp.price, io.current_price) - io.entry_price) / io.entry_price) * 100
                        END
                    ELSE io.current_return_pct
                END as current_return_pct,
                io.status,
                io.exit_price,
                io.exit_date,
                io.exit_reason,
                io.realized_return_pct,
                io.holding_days,
                io.max_favorable_pct,
                io.max_adverse_pct,
                NULL as thesis,
                NULL as confidence_score,
                NULL as risk_level
            FROM idea_outcomes io
            LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
            WHERE io.idea_id = ?
        """

        with storage.connection() as conn:
            row = conn.execute(query, [trade_id]).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Paper trade {trade_id} not found",
            )

        trade = PaperTradeResponse(
            idea_id=str(row[0]) if row[0] else "",
            agent_run_id=str(row[1]) if row[1] else "",
            symbol=str(row[2]) if row[2] else "",
            idea_type=str(row[3]) if row[3] in ["buy", "sell"] else "buy",  # type: ignore[arg-type]
            entry_price=float(row[4]) if row[4] is not None else None,
            entry_date=str(row[5]) if row[5] else None,
            target_price=float(row[6]) if row[6] is not None else None,
            stop_loss_price=float(row[7]) if row[7] is not None else None,
            current_price=float(row[8]) if row[8] is not None else None,
            current_return_pct=float(row[9]) if row[9] is not None else None,
            status=str(row[10]) if row[10] else "",
            exit_price=float(row[11]) if row[11] is not None else None,
            exit_date=str(row[12]) if row[12] else None,
            exit_reason=str(row[13]) if row[13] else None,
            realized_return_pct=float(row[14]) if row[14] is not None else None,
            holding_days=int(row[15]) if row[15] is not None else None,
            max_favorable_pct=float(row[16]) if row[16] is not None else None,
            max_adverse_pct=float(row[17]) if row[17] is not None else None,
            thesis=str(row[18]) if row[18] else None,
            confidence_score=float(row[19]) if row[19] is not None else None,
            risk_level=str(row[20]) if row[20] else None,
        )

        logger.info("paper_trade_retrieved", trade_id=trade_id, symbol=trade.symbol)

        return trade

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_get_paper_trade", trade_id=trade_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch paper trade: {e}",
        ) from e


@router.post("/{trade_id}/close", response_model=CloseTradeResponse)
async def close_paper_trade(
    trade_id: str,
    request: CloseTradeRequest,
) -> CloseTradeResponse:
    """Manually close an open paper trade.

    Path Parameters:
        trade_id: The idea_id of the paper trade to close

    Request Body:
        exit_price: Optional exit price (uses current_price if not provided)
        exit_reason: Reason for closing (default: "manual")

    Returns:
        Result of close operation with realized P&L
    """
    try:
        with storage.connection() as conn:
            # Get trade info with live price from price_cache
            trade_row = conn.execute(
                """
                WITH latest_prices AS (
                    SELECT DISTINCT ON (symbol)
                        symbol,
                        price
                    FROM price_cache
                    WHERE cached_at >= NOW() - INTERVAL '1 hour'
                    ORDER BY symbol, cached_at DESC
                )
                SELECT
                    io.symbol,
                    io.entry_price,
                    COALESCE(lp.price, io.current_price) as current_price,
                    io.status,
                    io.shares
                FROM idea_outcomes io
                LEFT JOIN latest_prices lp ON lp.symbol = io.symbol
                WHERE io.idea_id = ?
                """,
                [trade_id],
            ).fetchone()

            if not trade_row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Paper trade {trade_id} not found",
                )

            symbol, entry_price, current_price, status, shares = trade_row

            if status != "open":
                raise HTTPException(
                    status_code=400,
                    detail=f"Trade is already {status}, cannot close",
                )

            # Determine exit price - use live price from cache if not explicitly provided
            exit_price = request.exit_price if request.exit_price is not None else current_price

            if exit_price is None or entry_price is None:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot close trade: missing price data",
                )

            # Calculate realized return
            realized_return_pct = (
                (float(exit_price) - float(entry_price)) / float(entry_price)
            ) * 100

            # Update trade
            exit_date = date.today().isoformat()
            conn.execute(
                """
                UPDATE idea_outcomes
                SET
                    status = 'closed',
                    exit_price = ?,
                    exit_date = ?,
                    exit_reason = ?,
                    realized_return_pct = ?
                WHERE idea_id = ?
                """,
                [exit_price, exit_date, request.exit_reason, realized_return_pct, trade_id],
            )
            conn.commit()

        # Return proceeds to cash balance
        # Type narrow: shares is str | int | float from DB, check it's a positive number
        if shares is not None and (isinstance(shares, (int, float)) and shares > 0):
            exit_amount = float(shares) * float(exit_price)
            cash_manager = CashManager(storage)
            cash_manager.add_cash(
                "paper_trading",
                exit_amount,
                f"Sell {shares} {symbol} @ ${exit_price:.2f}",
            )

        logger.info(
            "paper_trade_closed",
            trade_id=trade_id,
            symbol=symbol,
            exit_price=exit_price,
            realized_return_pct=realized_return_pct,
        )

        return CloseTradeResponse(
            status="closed",
            trade_id=trade_id,
            symbol=str(symbol),
            exit_price=float(exit_price),
            exit_date=str(exit_date),
            realized_return_pct=float(realized_return_pct),
            message=f"Successfully closed {symbol} trade with {realized_return_pct:+.2f}% return",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_close_trade", trade_id=trade_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to close trade: {e}",
        ) from e


@router.post("/account/reset", response_model=ResetAccountResponse)
async def reset_paper_account(request: ResetAccountRequest) -> ResetAccountResponse:
    """Reset the paper trading account to starting balance.

    This will:
    1. Optionally close all open trades (at current prices)
    2. Reset cash balance to initial_cash (or new_starting_balance if provided)
    3. Optionally update the starting balance

    Request Body:
        new_starting_balance: Optional new starting balance
        close_open_trades: Whether to close open trades (default: True)

    Returns:
        Result of reset operation
    """
    try:
        with storage.connection() as conn:
            # Get current balance
            account_row = conn.execute(
                """
                SELECT cash_balance, initial_cash
                FROM portfolio_accounts
                WHERE id = 'paper_trading'
                """
            ).fetchone()

            if not account_row:
                raise HTTPException(status_code=404, detail="Paper trading account not found")

            # Type narrow: account_row[0] and account_row[1] are DB values (str | int | float | bool | None)
            if account_row[0] is None or account_row[1] is None:
                raise HTTPException(
                    status_code=500, detail="Account balance data is corrupted (NULL values)"
                )
            previous_balance = float(account_row[0])
            current_initial = float(account_row[1])

            trades_closed = 0

            # Close open trades if requested
            if request.close_open_trades:
                # Count open trades
                count_row = conn.execute(
                    "SELECT COUNT(*) FROM idea_outcomes WHERE status = 'open'"
                ).fetchone()
                # Type narrow: count_row[0] is a DB value (str | int | float | bool | None)
                trades_closed = int(count_row[0]) if count_row and count_row[0] is not None else 0

                # Close all open trades
                if trades_closed > 0:
                    exit_date = date.today().isoformat()
                    conn.execute(
                        """
                        UPDATE idea_outcomes
                        SET
                            status = 'closed',
                            exit_price = COALESCE(current_price, entry_price),
                            exit_date = ?,
                            exit_reason = 'account_reset',
                            realized_return_pct = CASE
                                WHEN entry_price > 0 THEN
                                    ((COALESCE(current_price, entry_price) - entry_price) / entry_price) * 100
                                ELSE 0
                            END
                        WHERE status = 'open'
                        """,
                        [exit_date],
                    )

            # Determine new balance
            new_balance = request.new_starting_balance or current_initial

            # Update account
            conn.execute(
                """
                UPDATE portfolio_accounts
                SET
                    cash_balance = ?,
                    initial_cash = ?,
                    updated_at = NOW()
                WHERE id = 'paper_trading'
                """,
                [new_balance, new_balance],
            )
            conn.commit()

        logger.info(
            "paper_account_reset",
            previous_balance=previous_balance,
            new_balance=new_balance,
            trades_closed=trades_closed,
        )

        return ResetAccountResponse(
            status="reset",
            previous_balance=previous_balance,
            new_balance=new_balance,
            trades_closed=trades_closed,
            message=f"Account reset to ${new_balance:,.2f}. {trades_closed} trades closed.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_reset_account", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset account: {e}",
        ) from e


@router.patch("/account/settings", response_model=UpdateSettingsResponse)
async def update_paper_settings(request: UpdateSettingsRequest) -> UpdateSettingsResponse:
    """Update paper trading account settings.

    Currently supports updating the starting balance without resetting.

    Request Body:
        starting_balance: New starting balance amount

    Returns:
        Updated settings
    """
    try:
        with storage.connection() as conn:
            # Get current balance
            account_row = conn.execute(
                """
                SELECT cash_balance
                FROM portfolio_accounts
                WHERE id = 'paper_trading'
                """
            ).fetchone()

            if not account_row:
                raise HTTPException(status_code=404, detail="Paper trading account not found")

            # Type narrow: account_row[0] is a DB value (str | int | float | bool | None)
            if account_row[0] is None:
                raise HTTPException(
                    status_code=500, detail="Account balance data is corrupted (NULL value)"
                )
            current_cash = float(account_row[0])

            # Update initial_cash only (not current balance)
            conn.execute(
                """
                UPDATE portfolio_accounts
                SET
                    initial_cash = ?,
                    updated_at = NOW()
                WHERE id = 'paper_trading'
                """,
                [request.starting_balance],
            )
            conn.commit()

        logger.info(
            "paper_settings_updated",
            starting_balance=request.starting_balance,
        )

        return UpdateSettingsResponse(
            status="updated",
            starting_balance=request.starting_balance,
            cash_balance=current_cash,
            message=f"Starting balance updated to ${request.starting_balance:,.2f}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_update_settings", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update settings: {e}",
        ) from e

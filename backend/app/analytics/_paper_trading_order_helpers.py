"""Private helpers for paper trading order creation.

Internal module - do not import directly from outside analytics package.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime

from app.analytics.cash_manager import CashManager
from app.analytics.types import PaperTradeDict
from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def fetch_strategy_metrics(
    storage: PortfolioStorage, strategy_id: str
) -> tuple[float | None, float | None, float | None]:
    """Return (sharpe, win_rate, max_drawdown) for a strategy, or (None, None, None) on error."""
    try:
        with storage.connection() as conn:
            row = conn.execute(
                """SELECT expected_sharpe, expected_win_rate, expected_max_drawdown
                   FROM strategy_definitions WHERE id = %s""",
                (strategy_id,),
            ).fetchone()
            if row:
                return (
                    float(row[0]) if row[0] else None,
                    float(row[1]) if row[1] else None,
                    float(row[2]) if row[2] else None,
                )
    except Exception as e:
        logger.warning(f"Failed to fetch strategy metrics: {e}")
    return (None, None, None)


def validate_strategy_metrics(
    strategy_id: str,
    symbol: str,
    sharpe: float | None,
    win_rate: float | None,
    min_sharpe: float,
    min_win_rate: float,
) -> bool:
    """Return True if strategy metrics pass validation gates."""
    if sharpe is None:
        logger.warning(
            "paper_trade_rejected_no_backtest", strategy_id=strategy_id, symbol=symbol,
            reason="No backtest metrics found for strategy",
        )
        return False
    if sharpe < min_sharpe:
        logger.warning(
            "paper_trade_rejected_low_sharpe", strategy_id=strategy_id, symbol=symbol,
            backtest_sharpe=sharpe, min_sharpe=min_sharpe,
        )
        return False
    if win_rate is not None and win_rate < min_win_rate:
        logger.warning(
            "paper_trade_rejected_low_win_rate", strategy_id=strategy_id, symbol=symbol,
            backtest_win_rate=win_rate, min_win_rate=min_win_rate,
        )
        return False
    return True


def build_strategy_trade_dict(
    idea_id: str,
    strategy_id: str,
    symbol: str,
    entry_price: float,
    stop_loss_price: float,
    shares: int,
    entry_amount: float,
    backtest_sharpe: float | None,
    backtest_win_rate: float | None,
    backtest_max_drawdown: float | None,
    backtest_run_id: str | None,
) -> PaperTradeDict:
    """Build the PaperTradeDict for a strategy-signal-based trade."""
    now = datetime.now(UTC)
    return {  # type: ignore[return-value]
        "idea_id": idea_id,
        "agent_run_id": f"strategy:{strategy_id}",
        "symbol": symbol,
        "idea_type": "buy",
        "entry_price": entry_price,
        "entry_date": dt.date.today(),
        "target_price": entry_price * 1.15,
        "stop_loss_price": stop_loss_price,
        "current_price": entry_price,
        "current_return_pct": 0.0,
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "exit_reason": None,
        "realized_return_pct": None,
        "holding_days": 0,
        "max_favorable_pct": 0.0,
        "max_adverse_pct": 0.0,
        "created_at": now,
        "updated_at": now,
        "strategy_id": strategy_id,
        "shares": shares,
        "entry_amount": entry_amount,
        "backtest_sharpe": backtest_sharpe,
        "backtest_win_rate": backtest_win_rate,
        "backtest_max_drawdown": backtest_max_drawdown,
        "backtest_run_id": backtest_run_id,
    }


def insert_strategy_trade_records(
    storage: PortfolioStorage,
    idea_id: str,
    strategy_id: str,
    symbol: str,
    signal_strength: int,
    signal_reasons: list[str] | None,
    insert_data: PaperTradeDict,
) -> None:
    """Insert agent_run, agent_ideas, and idea_outcomes records for a strategy trade."""
    agent_run_id = f"strategy:{strategy_id}"
    now = datetime.now(UTC)
    thesis = f"Auto-generated from strategy signal. Strength: {signal_strength}/10. "
    if signal_reasons:
        thesis += "Reasons: " + ", ".join(signal_reasons[:3])
    _ensure_agent_run(storage, agent_run_id, strategy_id, now)
    storage.insert_dict(
        "agent_ideas",
        {
            "id": idea_id,
            "agent_run_id": agent_run_id,
            "idea_type": "buy",
            "title": f"Buy {symbol}",
            "thesis": thesis,
            "action": f"Buy {symbol}",
            "confidence_score": signal_strength / 10.0,
            "risk_level": "medium",
            "status": "pending",
            "created_at": now.isoformat(),
        },
    )
    storage.insert_dict("idea_outcomes", dict(insert_data))  # type: ignore[arg-type]


def acquire_position(
    storage: PortfolioStorage,
    strategy_id: str,
    symbol: str,
    entry_price: float,
    position_pct: float = 0.05,
) -> tuple[int, float] | None:
    """Calculate shares, deduct cash; return (shares, entry_amount) or None on failure."""
    cash_manager = CashManager(storage)
    account_id = "paper_trading"
    try:
        cash_balance = cash_manager.get_cash_balance(account_id)
    except ValueError:
        logger.warning("paper_trade_blocked_no_account", strategy_id=strategy_id, symbol=symbol)
        return None

    shares = int((cash_balance * position_pct) / entry_price)
    if shares <= 0:
        logger.warning(
            "paper_trade_blocked_insufficient_funds", strategy_id=strategy_id, symbol=symbol,
            cash_balance=cash_balance, entry_price=entry_price,
        )
        return None

    entry_amount = shares * entry_price
    if not cash_manager.deduct_cash(account_id, entry_amount, f"Buy {shares} {symbol}"):
        logger.warning(
            "paper_trade_blocked_cash_deduction_failed", strategy_id=strategy_id, symbol=symbol,
            entry_amount=entry_amount,
        )
        return None
    return (shares, entry_amount)


def _ensure_agent_run(
    storage: PortfolioStorage, agent_run_id: str, strategy_id: str, now: datetime
) -> None:
    """Create agent_run record if it does not already exist."""
    with storage.connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM agent_runs WHERE id = %s", (agent_run_id,)
        ).fetchone()
        if not exists:
            conn.execute(
                """INSERT INTO agent_runs (id, session_id, agent_type, status, started_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (agent_run_id, f"strategy-signal-{strategy_id[:8]}", "strategy_signal", "completed", now),
            )
            conn.commit()

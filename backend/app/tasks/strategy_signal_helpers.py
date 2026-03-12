"""Helper functions for strategy signal generation tasks."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger
from app.watchlist.models import SignalInputsDict

logger = get_logger(__name__)


def _query_price_and_indicators(conn: Any, symbol: str) -> list[Any]:
    """Fetch the two most recent price and indicator rows for a symbol."""
    return conn.execute(
        """
        SELECT
            db.close as price,
            db.volume,
            ti.ema_20,
            ti.sma_5,
            ti.sma_20,
            ti.rsi_14,
            ti.macd as macd_line,
            ti.macd_signal,
            ti.atr_14 as volume_avg_20,
            db.date as data_date
        FROM day_bars db
        LEFT JOIN technical_indicators ti ON db.symbol = ti.symbol AND db.date = ti.date
        WHERE db.symbol = %s
        ORDER BY db.date DESC
        LIMIT 2
        """,
        (symbol,),
    ).fetchall()


def _query_fundamentals(conn: Any, symbol: str) -> Any | None:
    """Fetch the most recent fundamentals from reference_cache."""
    return conn.execute(
        """
        SELECT payload->>'profit_margin' as profit_margin,
               payload->>'revenue_growth' as revenue_growth,
               payload->>'debt_to_equity' as debt_to_equity
        FROM reference_cache
        WHERE symbol = %s
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()


def _query_sentiment(conn: Any, symbol: str) -> Any | None:
    """Fetch 7-day average news sentiment for a symbol."""
    return conn.execute(
        """
        SELECT AVG(sentiment_score) as avg_sentiment
        FROM news_cache
        WHERE symbol = %s
        AND published_at >= NOW() - INTERVAL '7 days'
        """,
        (symbol,),
    ).fetchone()


def _query_health(conn: Any, symbol: str) -> Any | None:
    """Fetch company health from watchlist_items."""
    return conn.execute(
        """
        SELECT metadata->>'company_health' as company_health
        FROM watchlist_items
        WHERE symbol = %s
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()


def _build_market_data_dict(
    current: Any,
    previous: Any,
    fundamentals: Any | None,
    sentiment: Any | None,
    health: Any | None,
) -> dict[str, Any]:
    """Assemble a market data dict from query row results."""
    return {
        "price": float(current[0]) if current[0] else 0.0,
        "volume": int(current[1]) if current[1] else 0,
        "ema_20": float(current[2]) if current[2] else None,
        "sma_5": float(current[3]) if current[3] else None,
        "sma_5_prev": float(previous[3]) if previous[3] else None,
        "sma_20": float(current[4]) if current[4] else None,
        "rsi_14": float(current[5]) if current[5] else None,
        "macd": float(current[6]) if current[6] else None,
        "macd_signal": float(current[7]) if current[7] else None,
        "volume_avg_20": float(current[8]) if current[8] else None,
        "data_date": current[9].isoformat() if current[9] else None,
        "profit_margin": float(fundamentals[0]) if fundamentals and fundamentals[0] else None,
        "revenue_growth": float(fundamentals[1]) if fundamentals and fundamentals[1] else None,
        "debt_to_equity": float(fundamentals[2]) if fundamentals and fundamentals[2] else None,
        "news_sentiment": float(sentiment[0]) if sentiment and sentiment[0] else 0.0,
        "company_health": health[0] if health and health[0] else "UNKNOWN",
    }


def fetch_current_market_data(conn: Any, symbol: str) -> dict[str, Any] | None:
    """Fetch current market data for a symbol.

    Returns dict with price, technicals, fundamentals or None if unavailable.
    """
    result = _query_price_and_indicators(conn, symbol)
    if not result or len(result) < 2:
        logger.warning("insufficient_market_data", symbol=symbol)
        return None

    return _build_market_data_dict(
        current=result[0],
        previous=result[1],
        fundamentals=_query_fundamentals(conn, symbol),
        sentiment=_query_sentiment(conn, symbol),
        health=_query_health(conn, symbol),
    )


def build_signal_inputs(market_data: dict[str, Any]) -> SignalInputsDict:
    """Build SignalInputsDict from market data."""
    return SignalInputsDict(
        price=market_data.get("price", 0.0),
        ema_20=market_data.get("ema_20"),
        sma_5=market_data.get("sma_5"),
        sma_5_prev=market_data.get("sma_5_prev"),
        rsi_14=market_data.get("rsi_14"),
        macd=market_data.get("macd"),
        volume=market_data.get("volume", 0),
        volume_avg_20=market_data.get("volume_avg_20"),
        company_health=market_data.get("company_health", "UNKNOWN"),
        news_sentiment=market_data.get("news_sentiment", 0.0),
        earnings_days_away=None,
        profit_margin=market_data.get("profit_margin"),
        revenue_growth=market_data.get("revenue_growth"),
        debt_to_equity=market_data.get("debt_to_equity"),
        recommendation_mean=None,
        analyst_buy_pct=None,
        options_call_pct=None,
        options_near_term_pct=None,
        symbol_in_active_sector=False,
        earnings_surprise_score=None,
        earnings_surprise_reasons=None,
    )


def store_signal(conn: Any, signal_data: dict[str, Any]) -> str | None:
    """Store a generated signal in the database.

    Returns signal ID or None if storage failed.
    """
    if "error" in signal_data:
        return None

    try:
        conn.execute(
            """
            INSERT INTO symbols (symbol, security_type, created_at)
            VALUES (%s, 'equity', NOW())
            ON CONFLICT (symbol) DO NOTHING
            """,
            (signal_data["symbol"],),
        )
        result = conn.execute(
            """
            INSERT INTO strategy_signals (
                strategy_id, symbol, signal_date, signal_type,
                signal_strength, reasons, market_data
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (strategy_id, signal_date) DO UPDATE SET
                signal_type = EXCLUDED.signal_type,
                signal_strength = EXCLUDED.signal_strength,
                reasons = EXCLUDED.reasons,
                market_data = EXCLUDED.market_data,
                created_at = NOW()
            RETURNING id
            """,
            (
                signal_data["strategy_id"],
                signal_data["symbol"],
                date.today(),
                signal_data["signal_type"],
                signal_data["signal_strength"],
                signal_data["reasons"],
                json.dumps(signal_data["market_data"]),
            ),
        ).fetchone()
        return str(result[0]) if result else None
    except Exception as e:
        logger.exception("Failed to store signal", error=str(e))
        return None


def make_empty_signal_results(strategies_evaluated: int) -> dict[str, Any]:
    """Build a fresh results dict for signal generation."""
    return {
        "status": "completed",
        "strategies_evaluated": strategies_evaluated,
        "signals_generated": 0,
        "buy_signals": 0,
        "sell_signals": 0,
        "hold_signals": 0,
        "errors": [],
    }


def record_signal_result(results: dict[str, Any], signal_data: dict[str, Any]) -> None:
    """Update results counters based on signal type."""
    results["signals_generated"] += 1
    signal_type = signal_data["signal_type"]
    if signal_type == "BUY":
        results["buy_signals"] += 1
    elif signal_type == "SELL":
        results["sell_signals"] += 1
    else:
        results["hold_signals"] += 1


def record_signal_error(
    results: dict[str, Any], strategy_id: str, symbol: str, error: str
) -> None:
    """Append an error entry to the results error list."""
    results["errors"].append(
        {"strategy_id": strategy_id, "symbol": symbol, "error": error}
    )


def query_todays_buy_signals(conn: Any, min_signal_strength: int) -> list[Any]:
    """Fetch today's BUY signals meeting the minimum strength threshold."""
    return conn.execute(
        """
        SELECT
            ss.strategy_id,
            ss.symbol,
            ss.signal_type,
            ss.signal_strength,
            ss.reasons,
            sd.name as strategy_name
        FROM strategy_signals ss
        JOIN strategy_definitions sd ON ss.strategy_id = sd.id
        WHERE ss.signal_date = CURRENT_DATE
          AND ss.signal_type = 'BUY'
          AND ss.signal_strength >= %s
          AND sd.status = 'active'
        ORDER BY ss.signal_strength DESC
        """,
        (min_signal_strength,),
    ).fetchall()


def has_open_position(conn: Any, strategy_id: str, symbol: str) -> bool:
    """Return True if there is already an open position for strategy+symbol."""
    row = conn.execute(
        """
        SELECT idea_id
        FROM idea_outcomes
        WHERE strategy_id = %s
          AND symbol = %s
          AND status = 'open'
        LIMIT 1
        """,
        (strategy_id, symbol),
    ).fetchone()
    return row is not None


def _attempt_paper_trade(
    storage: Any,
    strategy_id: str,
    symbol: str,
    strategy_name: str,
    signal_strength: int,
    reasons: list[str],
    results: dict[str, Any],
) -> None:
    """Create a paper trade and update results counters."""
    from app.analytics.paper_trading_orders import create_paper_trade_from_strategy_signal

    trade = create_paper_trade_from_strategy_signal(
        storage=storage,
        strategy_id=strategy_id,
        symbol=symbol,
        signal_strength=signal_strength,
        signal_reasons=reasons,
    )
    if trade:
        results["trades_created"] += 1
        logger.info(
            "Paper trade created",
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            entry_price=trade["entry_price"],
        )
    else:
        results["rejected_validation"] += 1
        logger.info("Trade rejected by validation", strategy_id=strategy_id, symbol=symbol)


def process_paper_trade_signal(
    conn: Any,
    storage: Any,
    signal: Any,
    results: dict[str, Any],
) -> None:
    """Evaluate one BUY signal and create a paper trade if appropriate."""
    strategy_id = str(signal[0])
    symbol = str(signal[1])
    signal_strength = int(signal[3]) if signal[3] is not None else 0
    reasons: list[str] = signal[4] if isinstance(signal[4], list) else []
    strategy_name = str(signal[5])

    try:
        if has_open_position(conn, strategy_id, symbol):
            logger.info("Skipping - open position exists", strategy_id=strategy_id, symbol=symbol)
            results["skipped_existing_position"] += 1
            return
        _attempt_paper_trade(storage, strategy_id, symbol, strategy_name, signal_strength, reasons, results)
    except Exception as e:
        logger.exception("Error processing signal", strategy_id=strategy_id, symbol=symbol, error=str(e))
        results["errors"].append({"strategy_id": strategy_id, "symbol": symbol, "error": str(e)})



def make_signal_result(
    strategy_id: str,
    symbol: str,
    signal_type: str,
    signal_strength: Any,
    reasons: list[str],
    market_data: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the signal result dict."""
    return {
        "strategy_id": strategy_id,
        "symbol": symbol,
        "signal_type": signal_type,
        "signal_strength": signal_strength,
        "reasons": reasons,
        "market_data": market_data,
        "generated_at": datetime.now(UTC).isoformat(),
    }

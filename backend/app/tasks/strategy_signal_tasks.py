"""Strategy signal generation tasks.

Generates daily trading signals for active strategies by evaluating
current market conditions against strategy parameters.

Schedule: Daily at 15:00 UTC (after US market close)
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.storage import get_strategy_storage
from app.watchlist.models import SignalInputsDict
from app.watchlist.signal_classifier import classify_signal

logger = get_logger(__name__)


def _fetch_current_market_data(conn: Any, symbol: str) -> dict[str, Any] | None:
    """Fetch current market data for a symbol.

    Returns dict with price, technicals, fundamentals or None if data unavailable.
    """
    # Get latest price and technical indicators
    result = conn.execute(
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

    if not result or len(result) < 2:
        logger.warning(f"Insufficient market data for {symbol}")
        return None

    current = result[0]
    previous = result[1]

    # Get fundamentals from reference_cache (stored in payload JSONB)
    fundamentals_row = conn.execute(
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
    fundamentals = fundamentals_row if fundamentals_row else None

    # Get news sentiment
    sentiment = conn.execute(
        """
        SELECT AVG(sentiment_score) as avg_sentiment
        FROM news_cache
        WHERE symbol = %s
        AND published_at >= NOW() - INTERVAL '7 days'
        """,
        (symbol,),
    ).fetchone()

    # Get company health from watchlist
    health = conn.execute(
        """
        SELECT metadata->>'company_health' as company_health
        FROM watchlist_items
        WHERE symbol = %s
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()

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


def _build_signal_inputs(market_data: dict[str, Any]) -> SignalInputsDict:
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
        earnings_days_away=None,  # Could add earnings calendar check
        profit_margin=market_data.get("profit_margin"),
        revenue_growth=market_data.get("revenue_growth"),
        debt_to_equity=market_data.get("debt_to_equity"),
        recommendation_mean=None,  # Could add analyst data
        analyst_buy_pct=None,
        options_call_pct=None,
        options_near_term_pct=None,
        symbol_in_active_sector=False,
        earnings_surprise_score=None,
        earnings_surprise_reasons=None,
    )


def generate_signal_for_strategy(strategy_id: str, symbol: str) -> dict[str, Any]:
    """Generate a trading signal for a specific strategy.

    Args:
        strategy_id: UUID of the strategy
        symbol: Stock symbol

    Returns:
        Dict with signal_type, strength, reasons, and market_data snapshot
    """
    conn_mgr = get_connection_manager()
    strategy_storage = get_strategy_storage()

    # Get strategy definition
    strategy = strategy_storage.get_strategy_by_id(strategy_id)
    if not strategy:
        return {"error": f"Strategy {strategy_id} not found"}

    if strategy.status != "active":
        return {"error": f"Strategy {strategy_id} is not active (status={strategy.status})"}

    with conn_mgr.connection() as conn:
        # Fetch current market data
        market_data = _fetch_current_market_data(conn, symbol)
        if not market_data:
            return {"error": f"No market data available for {symbol}"}

        # Build signal inputs
        signal_inputs = _build_signal_inputs(market_data)

        # Generate signal using the classifier
        signal = classify_signal(signal_inputs)

        # Determine if this is a SELL signal (for existing positions)
        # AVOID signals on existing positions should trigger exits
        signal_type = signal.signal_type.value
        if signal_type == "AVOID":
            signal_type = "SELL"  # Translate AVOID to SELL for clarity

        return {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "signal_type": signal_type,
            "signal_strength": signal.strength.value,
            "reasons": signal.reasons,
            "market_data": market_data,
            "generated_at": datetime.now(UTC).isoformat(),
        }


def store_signal(conn: Any, signal_data: dict[str, Any]) -> str | None:
    """Store a generated signal in the database.

    Returns signal ID or None if storage failed.
    """
    if "error" in signal_data:
        return None

    try:
        # Ensure symbol exists in symbols table (FK constraint)
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
                signal_data["reasons"],  # PostgreSQL handles list -> TEXT[]
                json.dumps(signal_data["market_data"]),  # JSONB requires JSON string
            ),
        ).fetchone()
        return str(result[0]) if result else None
    except Exception as e:
        logger.exception("Failed to store signal", error=str(e))
        return None


def generate_daily_strategy_signals() -> dict[str, Any]:
    """Generate signals for all active strategies.

    Schedule: Daily at 15:00 UTC (after US market close)

    Returns:
        Summary dict with counts and any errors
    """
    logger.info("Starting daily strategy signal generation")

    conn_mgr = get_connection_manager()
    strategy_storage = get_strategy_storage()

    # Get all active strategies
    active_strategies = strategy_storage.list_strategies(status="active", limit=100)

    if not active_strategies:
        logger.info("No active strategies found")
        return {
            "status": "completed",
            "strategies_evaluated": 0,
            "signals_generated": 0,
            "buy_signals": 0,
            "sell_signals": 0,
            "errors": [],
        }

    logger.info(f"Evaluating {len(active_strategies)} active strategies")

    results: dict[str, Any] = {
        "status": "completed",
        "strategies_evaluated": len(active_strategies),
        "signals_generated": 0,
        "buy_signals": 0,
        "sell_signals": 0,
        "hold_signals": 0,
        "errors": [],
    }

    with conn_mgr.connection() as conn:
        for strategy in active_strategies:
            try:
                signal_data = generate_signal_for_strategy(strategy.id, strategy.symbol)

                if "error" in signal_data:
                    results["errors"].append(
                        {
                            "strategy_id": strategy.id,
                            "symbol": strategy.symbol,
                            "error": signal_data["error"],
                        }
                    )
                    continue

                # Store signal
                signal_id = store_signal(conn, signal_data)
                if signal_id:
                    results["signals_generated"] += 1

                    if signal_data["signal_type"] == "BUY":
                        results["buy_signals"] += 1
                    elif signal_data["signal_type"] == "SELL":
                        results["sell_signals"] += 1
                    else:
                        results["hold_signals"] += 1

                    logger.info(
                        "Signal generated",
                        strategy_id=strategy.id,
                        symbol=strategy.symbol,
                        signal_type=signal_data["signal_type"],
                        strength=signal_data["signal_strength"],
                    )

            except Exception as e:
                logger.exception(
                    "Failed to generate signal",
                    strategy_id=strategy.id,
                    symbol=strategy.symbol,
                    error=str(e),
                )
                results["errors"].append(
                    {
                        "strategy_id": strategy.id,
                        "symbol": strategy.symbol,
                        "error": str(e),
                    }
                )

        conn.commit()

    logger.info(
        "Daily signal generation completed",
        strategies=results["strategies_evaluated"],
        signals=results["signals_generated"],
        buy=results["buy_signals"],
        sell=results["sell_signals"],
        errors=len(results["errors"]),
    )

    return results


def generate_signal_for_strategy_task(strategy_id: str, symbol: str) -> dict[str, Any]:
    """Task wrapper for single strategy signal generation.

    Can be called on-demand via API.
    """
    return generate_signal_for_strategy(strategy_id, symbol)


def auto_paper_trade_from_signals(min_signal_strength: int = 5) -> dict[str, Any]:
    """Create paper trades from BUY signals.

    Schedule: Daily at 21:45 UTC (after signals generated)

    For each BUY signal with strength >= threshold:
    - Check if no existing open position for this strategy+symbol
    - Create paper trade linked to strategy

    Args:
        min_signal_strength: Minimum signal strength to trigger trade (0-10)

    Returns:
        Summary dict with counts and any errors
    """
    from app.analytics.paper_trading_orders import create_paper_trade_from_strategy_signal
    from app.storage import get_storage

    logger.info("Starting auto paper trade from signals", min_strength=min_signal_strength)

    conn_mgr = get_connection_manager()
    storage = get_storage()

    results: dict[str, Any] = {
        "status": "completed",
        "signals_evaluated": 0,
        "trades_created": 0,
        "skipped_existing_position": 0,
        "skipped_low_strength": 0,
        "rejected_validation": 0,  # Trades rejected due to backtest validation
        "errors": [],
    }

    with conn_mgr.connection() as conn:
        # Get today's BUY signals with sufficient strength
        signals = conn.execute(
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

        results["signals_evaluated"] = len(signals)
        logger.info(f"Found {len(signals)} BUY signals to evaluate")

        for signal in signals:
            strategy_id = str(signal[0])
            symbol = str(signal[1])
            signal_strength = int(signal[3]) if signal[3] is not None else 0
            reasons: list[str] = signal[4] if isinstance(signal[4], list) else []
            strategy_name = str(signal[5])

            try:
                # Check if open position already exists for this strategy+symbol
                existing = conn.execute(
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

                if existing:
                    logger.info(
                        "Skipping - open position exists",
                        strategy_id=strategy_id,
                        symbol=symbol,
                    )
                    results["skipped_existing_position"] += 1
                    continue

                # Create paper trade
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
                    # Trade was rejected (likely due to backtest validation)
                    results["rejected_validation"] += 1
                    logger.info(
                        "Trade rejected by validation",
                        strategy_id=strategy_id,
                        symbol=symbol,
                    )

            except Exception as e:
                logger.exception(
                    "Error processing signal",
                    strategy_id=strategy_id,
                    symbol=symbol,
                    error=str(e),
                )
                results["errors"].append(
                    {
                        "strategy_id": strategy_id,
                        "symbol": symbol,
                        "error": str(e),
                    }
                )

    logger.info(
        "Auto paper trading completed",
        signals=results["signals_evaluated"],
        trades=results["trades_created"],
        skipped=results["skipped_existing_position"],
        rejected_validation=results["rejected_validation"],
        errors=len(results["errors"]),
    )

    return results

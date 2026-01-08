"""Data fetching functions for symbol intelligence.

Fetches data from various sources: watchlist, portfolio, paper trades,
strategies, news, and market data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.storage.helpers import row_to_dict, rows_to_dicts

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage
    from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)


def get_watchlist_data(
    symbol: str, watchlist_service: WatchlistService
) -> dict[str, Any] | None:
    """Fetch watchlist data for symbol using the watchlist service."""
    try:
        items = watchlist_service.get_items_with_scores()
        for item in items:
            if item.get("symbol", "").upper() == symbol.upper():
                score = item.get("score") or {}

                result = {
                    "id": str(item.get("id")),
                    "symbol": item.get("symbol"),
                    "note": item.get("note"),
                    "overall_score": score.get("overall"),
                    "signal_type": item.get("signal_type"),
                    "signal_strength": item.get("signal_strength"),
                    "recommended_style": item.get("recommended_style"),
                    "style_confidence": item.get("style_confidence"),
                    "optimal_holding_period": item.get("optimal_holding_period"),
                    "risk_level": item.get("risk_level"),
                    "entry_price": item.get("entry_price"),
                    "stop_loss": item.get("stop_loss"),
                    "profit_target": item.get("profit_target"),
                    "position_size_shares": item.get("position_size_shares"),
                    "company_health": item.get("company_health"),
                    "earnings_date": item.get("earnings_date"),
                    "earnings_days_away": item.get("earnings_days_away"),
                    "timeframe_short_aligned": item.get("timeframe_short_aligned"),
                    "timeframe_long_aligned": item.get("timeframe_long_aligned"),
                    "volume_relative": item.get("volume_relative"),
                    "news_intelligence": item.get("news_intelligence"),
                    "priority_indicators": item.get("priority_indicators"),
                }

                # Extract pillar scores
                for pillar in ["price", "technical", "fundamental", "catalyst", "options_flow"]:
                    pillar_data = score.get(pillar) or {}
                    result[f"{pillar}_score"] = pillar_data.get("score")
                    result[f"{pillar}_sub_scores"] = pillar_data.get("sub_scores")
                    result[f"{pillar}_metadata"] = pillar_data.get("metadata")
                    result[f"{pillar}_stale"] = pillar_data.get("stale", False)

                # Performance pillar
                perf = score.get("performance_factor") or {}
                result["performance_score"] = perf.get("score")
                result["performance_sub_scores"] = perf.get("sub_scores")
                result["performance_metadata"] = perf.get("metadata")
                result["performance_stale"] = perf.get("stale", False)

                # Data quality
                dq = item.get("data_quality") or {}
                result["data_quality_overall_pct"] = dq.get("overall_pct")
                result["data_quality_pillars"] = dq.get("pillars")

                return result
        return None
    except Exception as e:
        logger.warning(f"Failed to get watchlist data for {symbol}: {e}")
        return None


def get_portfolio_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch portfolio position and context."""
    position = None
    summary = None

    try:
        with storage.connection() as conn:
            pos_result = conn.execute(
                """
                SELECT p.id, p.symbol, p.shares, p.cost_basis, p.position_type,
                       pc.price as current_price
                FROM portfolio_positions p
                LEFT JOIN price_cache pc ON UPPER(p.symbol) = UPPER(pc.symbol)
                WHERE UPPER(p.symbol) = UPPER(%s)
                """,
                [symbol],
            )
            pos_row = pos_result.fetchone()
            if pos_row and pos_result.description:
                position = row_to_dict(pos_row, pos_result.description)

            summary_result = conn.execute(
                """
                SELECT
                    COUNT(*) as num_holdings,
                    SUM(p.shares * COALESCE(pc.price, p.cost_basis)) as total_value
                FROM portfolio_positions p
                LEFT JOIN price_cache pc ON UPPER(p.symbol) = UPPER(pc.symbol)
                """
            )
            sum_row = summary_result.fetchone()
            if sum_row and summary_result.description:
                summary = row_to_dict(sum_row, summary_result.description)
    except Exception as e:
        logger.warning(f"Failed to get portfolio data for {symbol}: {e}")

    return {"position": position, "summary": summary}


def get_paper_trades_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch paper trading history for symbol."""
    trades = []
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    idea_id, symbol, shares, entry_price, entry_date,
                    exit_price, exit_date, exit_reason,
                    current_price, current_return_pct, realized_return_pct,
                    CASE WHEN exit_date IS NULL THEN 'open' ELSE 'closed' END as status,
                    EXTRACT(DAY FROM COALESCE(exit_date, NOW()) - entry_date)::int as holding_days
                FROM idea_outcomes
                WHERE UPPER(symbol) = UPPER(%s)
                ORDER BY entry_date DESC
                """,
                [symbol],
            )
            rows = result.fetchall()
            if rows and result.description:
                trades = rows_to_dicts(rows, result.description)
    except Exception as e:
        logger.warning(f"Failed to get paper trades data for {symbol}: {e}")

    closed = [t for t in trades if t.get("status") == "closed"]
    open_trade = next((t for t in trades if t.get("status") == "open"), None)

    wins = [t for t in closed if float(t.get("realized_return_pct") or 0) > 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else None
    avg_return = (
        sum(float(t.get("realized_return_pct") or 0) for t in closed) / len(closed)
        if closed
        else None
    )

    return {
        "trades": trades,
        "open_trade": open_trade,
        "closed_trades": closed,
        "win_rate": win_rate,
        "avg_return": avg_return,
    }


def get_strategies_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch active strategies for symbol."""
    strategies = []
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT
                    id, name, symbol, strategy_type, status,
                    expected_sharpe, live_sharpe_ratio, live_win_rate,
                    live_trades_count
                FROM strategy_definitions
                WHERE UPPER(symbol) = UPPER(%s)
                AND status IN ('active', 'testing')
                ORDER BY live_sharpe_ratio DESC NULLS LAST
                """,
                [symbol],
            )
            rows = result.fetchall()
            if rows and result.description:
                strategies = rows_to_dicts(rows, result.description)
    except Exception as e:
        logger.warning(f"Failed to get strategies data for {symbol}: {e}")

    return {
        "strategies": strategies,
        "active_count": len(strategies),
        "best": strategies[0] if strategies else None,
    }


def get_news_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch news sentiment for symbol."""
    try:
        with storage.connection() as conn:
            result = conn.execute(
                """
                SELECT symbol, sentiment_score, article_count, created_at
                FROM news_summary_log
                WHERE UPPER(symbol) = UPPER(%s)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [symbol],
            )
            row = result.fetchone()
            if row and result.description:
                return row_to_dict(row, result.description)
    except Exception as e:
        logger.warning(f"Failed to get news data for {symbol}: {e}")
    return {}


def get_market_data(storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch current market context."""
    fear_greed = None
    indicators: dict[str, Any] = {}

    try:
        with storage.connection() as conn:
            fg_result = conn.execute(
                """
                SELECT score, label, score_change
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
            )
            fg_row = fg_result.fetchone()
            if fg_row and fg_result.description:
                fear_greed = row_to_dict(fg_row, fg_result.description)
    except Exception as e:
        logger.warning(f"Failed to get fear/greed data: {e}")

    try:
        with storage.connection() as conn:
            ind_result = conn.execute(
                """
                SELECT symbol, close as price,
                       (close - LAG(close) OVER (PARTITION BY symbol ORDER BY date)) /
                       NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY date), 0) * 100 as daily_change
                FROM day_bars
                WHERE symbol IN ('^VIX', '^GSPC')
                AND date >= (SELECT MAX(date) - INTERVAL '2 days' FROM day_bars WHERE symbol = '^VIX')
                ORDER BY date DESC
                """
            )
            rows = ind_result.fetchall()
            if rows and ind_result.description:
                for r in rows_to_dicts(rows, ind_result.description):
                    if r["symbol"] not in indicators:
                        indicators[r["symbol"]] = r
    except Exception as e:
        logger.warning(f"Failed to get market indicators: {e}")

    return {
        "fear_greed": fear_greed,
        "vix": indicators.get("^VIX", {}).get("price"),
        "sp500_change": indicators.get("^GSPC", {}).get("daily_change"),
    }


def fetch_all_data(
    symbol: str,
    storage: PortfolioStorage,
    watchlist_service: WatchlistService,
    include_market: bool,
    include_paper_trades: bool,
    include_strategies: bool,
) -> dict[str, Any]:
    """Fetch all data sources for symbol intelligence.

    Returns dict with keys: watchlist, portfolio, paper_trades, strategies, news, market
    """
    return {
        "watchlist": get_watchlist_data(symbol, watchlist_service),
        "portfolio": get_portfolio_data(symbol, storage),
        "paper_trades": get_paper_trades_data(symbol, storage) if include_paper_trades else None,
        "strategies": get_strategies_data(symbol, storage) if include_strategies else None,
        "news": get_news_data(symbol, storage),
        "market": get_market_data(storage) if include_market else {},
    }

"""Data fetching functions for symbol intelligence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.storage.helpers import row_to_dict, rows_to_dicts

from .portfolio_context import fetch_symbol_portfolio_context

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage
    from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

_PILLARS = ["price", "technical", "fundamental", "catalyst", "options_flow"]


def _extract_pillar_scores(score: dict[str, Any]) -> dict[str, Any]:
    """Return flattened pillar score fields from a score dict."""
    result: dict[str, Any] = {}
    for pillar in _PILLARS:
        pillar_data = score.get(pillar) or {}
        result[f"{pillar}_score"] = pillar_data.get("score")
        result[f"{pillar}_sub_scores"] = pillar_data.get("sub_scores")
        result[f"{pillar}_metadata"] = pillar_data.get("metadata")
        result[f"{pillar}_stale"] = pillar_data.get("stale", False)

    perf = score.get("performance_factor") or {}
    result["performance_score"] = perf.get("score")
    result["performance_sub_scores"] = perf.get("sub_scores")
    result["performance_metadata"] = perf.get("metadata")
    result["performance_stale"] = perf.get("stale", False)
    return result


def _build_watchlist_result(item: dict[str, Any]) -> dict[str, Any]:
    """Build the watchlist result dict from a single watchlist item."""
    score = item.get("score") or {}
    dq = item.get("data_quality") or {}

    result: dict[str, Any] = {
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
        "recent_news": item.get("recent_news"),
        "priority_indicators": item.get("priority_indicators"),
        "data_quality_overall_pct": dq.get("overall_pct"),
        "data_quality_pillars": dq.get("pillars"),
    }
    result.update(_extract_pillar_scores(score))
    return result


def get_watchlist_data(symbol: str, watchlist_service: WatchlistService) -> dict[str, Any] | None:
    """Fetch watchlist data for symbol using the watchlist service."""
    try:
        items = watchlist_service.get_items_with_scores(include_decision=False)
        for item in items:
            if item.get("symbol", "").upper() == symbol.upper():
                return _build_watchlist_result(item)
        return None
    except Exception as e:
        logger.warning("watchlist_data_fetch_failed", symbol=symbol, error=str(e))
        return None


def get_portfolio_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch portfolio position and context."""
    positions_by_symbol, summary = fetch_symbol_portfolio_context(
        storage,
        [symbol],
    )
    return {"position": positions_by_symbol.get(symbol.upper()), "summary": summary}


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
        logger.warning("strategies_data_fetch_failed", symbol=symbol, error=str(e))

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
        logger.warning("news_data_fetch_failed", symbol=symbol, error=str(e))
    return {}


def _fetch_fear_greed(storage: PortfolioStorage) -> dict[str, Any] | None:
    """Fetch latest fear/greed row, return None on failure."""
    try:
        with storage.connection() as conn:
            fg_result = conn.execute(
                """
                SELECT score, label, score_change, as_of_date
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
            )
            fg_row = fg_result.fetchone()
            if fg_row and fg_result.description:
                return row_to_dict(fg_row, fg_result.description)
    except Exception as e:
        logger.warning("fear_greed_data_fetch_failed", error=str(e))
    return None


def _fetch_market_indicators(storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch VIX and S&P 500 indicator rows, return dict keyed by symbol."""
    indicators: dict[str, Any] = {}
    try:
        with storage.connection() as conn:
            ind_result = conn.execute(
                """
                SELECT symbol, close as price,
                       (close - LAG(close) OVER (PARTITION BY symbol ORDER BY date)) /
                       NULLIF(LAG(close) OVER (PARTITION BY symbol ORDER BY date), 0) * 100 as daily_change,
                       date
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
        logger.warning("market_indicators_fetch_failed", error=str(e))
    return indicators


def get_market_data(storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch current market context."""
    fear_greed = _fetch_fear_greed(storage)
    indicators = _fetch_market_indicators(storage)
    return {
        "fear_greed": fear_greed,
        "vix": indicators.get("^VIX", {}).get("price"),
        "vix_as_of_date": indicators.get("^VIX", {}).get("date"),
        "sp500_change": indicators.get("^GSPC", {}).get("daily_change"),
        "sp500_as_of_date": indicators.get("^GSPC", {}).get("date"),
        "fear_greed_as_of_date": (fear_greed or {}).get("as_of_date"),
    }


def fetch_all_data(
    symbol: str,
    storage: PortfolioStorage,
    watchlist_service: WatchlistService,
    include_market: bool,
    include_strategies: bool,
) -> dict[str, Any]:
    """Fetch all data sources for symbol intelligence.

    Returns dict with keys: watchlist, portfolio, strategies, news, market
    """
    return {
        "watchlist": get_watchlist_data(symbol, watchlist_service),
        "portfolio": get_portfolio_data(symbol, storage),
        "strategies": get_strategies_data(symbol, storage) if include_strategies else None,
        "news": get_news_data(symbol, storage),
        "market": get_market_data(storage) if include_market else {},
    }

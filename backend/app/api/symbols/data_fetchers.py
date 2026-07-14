"""Data fetching functions for symbol intelligence."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage.helpers import row_to_dict, rows_to_dicts
from app.utils.market_hours import get_market_status

from .portfolio_context import fetch_symbol_portfolio_context

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage
    from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

_PILLARS = ["price", "technical", "fundamental", "catalyst", "options_flow"]
_SYMBOL_QUOTE_MAX_AGE_MINUTES = 1

_SECTION_FAILURE_MESSAGES = {
    "quote": "Current quote is temporarily unavailable.",
    "watchlist": "Scores and signal evidence are temporarily unavailable.",
    "portfolio": "Portfolio position context is temporarily unavailable.",
    "strategies": "Strategy context is temporarily unavailable.",
    "news": "News context is temporarily unavailable.",
    "market": "Market context is temporarily unavailable.",
}


def _fetch_section(
    *,
    symbol: str,
    section: str,
    fetch: Callable[[], Any],
    fallback: Any,
    issues: list[dict[str, str]],
) -> Any:
    """Keep independent symbol sources usable when one source fails."""
    try:
        return fetch()
    except Exception as exc:
        logger.warning(
            "symbol_data_section_failed",
            symbol=symbol,
            section=section,
            error=str(exc),
        )
        issues.append(
            {
                "section": section,
                "message": _SECTION_FAILURE_MESSAGES[section],
            }
        )
        return fallback


def get_quote_data(
    symbol: str,
    storage: PortfolioStorage,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch the canonical current quote from price_cache / PriceDataFetcher."""
    normalized_symbol = symbol.upper().strip()
    if not normalized_symbol:
        return {}

    fetcher = PriceDataFetcher(storage)
    quote = fetcher.fetch_price_data(
        [normalized_symbol],
        force_refresh=force_refresh,
        max_age_minutes=_SYMBOL_QUOTE_MAX_AGE_MINUTES,
    ).get(normalized_symbol)

    fetch_error = quote.error if quote else None
    if quote is None or quote.price <= 0 or quote.error:
        cached = fetcher.fetch_cached_price_data(
            [normalized_symbol],
            max_age_minutes=None,
        ).get(normalized_symbol)
        quote = cached or quote

    if quote is None:
        return {
            "symbol": normalized_symbol,
            "price": None,
            "source": None,
            "cached_at": None,
            "session": None,
            "error": fetch_error or "Quote unavailable",
        }

    return {
        "symbol": quote.symbol,
        "price": quote.price if quote.price > 0 and not quote.error else None,
        "source": quote.source,
        "cached_at": quote.cached_at,
        "session": get_market_status(quote.cached_at),
        "error": fetch_error or quote.error,
    }


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
    items = watchlist_service.get_items_with_scores(include_decision=False)
    for item in items:
        if item.get("symbol", "").upper() == symbol.upper():
            return _build_watchlist_result(item)
    return None


def get_portfolio_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch portfolio position and context."""
    positions_by_symbol, summary = fetch_symbol_portfolio_context(
        storage,
        [symbol],
    )
    return {"position": positions_by_symbol.get(symbol.upper()), "summary": summary}


def get_strategies_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Return the retired strategy-lab payload shape."""
    strategies: list[dict[str, Any]] = []
    return {
        "strategies": strategies,
        "active_count": 0,
        "best": None,
    }


def get_news_data(symbol: str, storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch news sentiment for symbol."""
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


def _fetch_canonical_vix(storage: PortfolioStorage) -> tuple[float | None, Any]:
    """Latest VIX level from the canonical price cache.

    The Today macro read sources VIX from price_cache (the canonical current
    quote). Reading it the same way here keeps the symbol page and Today from
    ever showing two different VIX values for the same day.
    """
    try:
        quote = (
            PriceDataFetcher(storage)
            .fetch_cached_price_data(["^VIX"], max_age_minutes=None)
            .get("^VIX")
        )
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("canonical_vix_fetch_failed", error=str(e))
        return None, None
    if quote is None or quote.price is None or quote.price <= 0:
        return None, None
    stamp = quote.quote_time or quote.cached_at
    return float(quote.price), (stamp.date() if stamp else None)


def get_market_data(storage: PortfolioStorage) -> dict[str, Any]:
    """Fetch current market context."""
    fear_greed = _fetch_fear_greed(storage)
    indicators = _fetch_market_indicators(storage)
    vix_value, vix_as_of = _fetch_canonical_vix(storage)
    if vix_value is None:
        # Canonical cache miss — fall back to the daily bar so VIX still renders.
        vix_value = indicators.get("^VIX", {}).get("price")
        vix_as_of = indicators.get("^VIX", {}).get("date")
    return {
        "fear_greed": fear_greed,
        "vix": vix_value,
        "vix_as_of_date": vix_as_of,
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
    *,
    force_quote_refresh: bool = False,
) -> dict[str, Any]:
    """Fetch all data sources for symbol intelligence.

    Returns independent section payloads plus structured section issues.
    """
    issues: list[dict[str, str]] = []
    quote = _fetch_section(
        symbol=symbol,
        section="quote",
        fetch=lambda: get_quote_data(symbol, storage, force_refresh=force_quote_refresh),
        fallback={},
        issues=issues,
    )
    watchlist = _fetch_section(
        symbol=symbol,
        section="watchlist",
        fetch=lambda: get_watchlist_data(symbol, watchlist_service),
        fallback=None,
        issues=issues,
    )
    portfolio = _fetch_section(
        symbol=symbol,
        section="portfolio",
        fetch=lambda: get_portfolio_data(symbol, storage),
        fallback={},
        issues=issues,
    )
    strategies = (
        _fetch_section(
            symbol=symbol,
            section="strategies",
            fetch=lambda: get_strategies_data(symbol, storage),
            fallback=None,
            issues=issues,
        )
        if include_strategies
        else None
    )

    has_watchlist_news = bool(
        watchlist
        and (watchlist.get("news_intelligence") or watchlist.get("recent_news"))
    )
    news = (
        {}
        if has_watchlist_news
        else _fetch_section(
            symbol=symbol,
            section="news",
            fetch=lambda: get_news_data(symbol, storage),
            fallback={},
            issues=issues,
        )
    )
    market = (
        _fetch_section(
            symbol=symbol,
            section="market",
            fetch=lambda: get_market_data(storage),
            fallback={},
            issues=issues,
        )
        if include_market
        else {}
    )

    return {
        "quote": quote,
        "watchlist": watchlist,
        "portfolio": portfolio,
        "strategies": strategies,
        "news": news,
        "market": market,
        "section_issues": issues,
    }

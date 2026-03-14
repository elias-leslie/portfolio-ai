"""Data fetching functions for watchlist refresh operations.

Handles: fundamentals/earnings, volume, news sentiment, price changes, backfill detection.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..analytics.news_sentiment_aggregator import get_symbol_sentiment
from ..logging_config import get_logger
from ..services import NewsService
from ..services.news_models import NewsBundle
from ..storage import PortfolioStorage
from .earnings import fetch_earnings_date_cached
from .fundamentals import (
    FundamentalData,
    calculate_fundamental_score,
    calculate_growth_score,
    calculate_health_score,
    calculate_sentiment_score,
    calculate_valuation_score,
    classify_company_health,
    fetch_fundamentals_cached,
)

logger = get_logger(__name__)


def calculate_price_change(
    storage: PortfolioStorage, symbol: str, price: float | None, item_id: str | None = None
) -> tuple[float | None, bool]:
    """Return (change_pct, has_historical_data); prefers day_bars, falls back to snapshot."""
    if price is None or price <= 0:
        return (None, False)

    df = storage.query(
        "SELECT close FROM day_bars WHERE symbol = ? ORDER BY date DESC LIMIT 2", [symbol]
    )
    if df.height >= 2 and df["close"][1] not in (0, None):
        return (float((price - df["close"][1]) / df["close"][1] * 100.0), True)

    if item_id:
        snap = storage.query(
            "SELECT price FROM watchlist_snapshots_v WHERE item_id = ? ORDER BY fetched_at DESC LIMIT 1",
            [item_id],
        )
        if snap.height > 0 and snap["price"][0] and snap["price"][0] > 0:
            prev = snap["price"][0]
            return (float((price - prev) / prev * 100.0), False)

    return (None, False)


def detect_missing_historical_data(
    storage: PortfolioStorage,
    symbols: list[str],
    min_days: int = 30,
    stale_threshold_days: int = 7,
) -> list[str]:
    """Return symbols lacking sufficient day_bars (no data, < min_days, or stale)."""
    if not symbols:
        return []
    with storage.connection() as conn:
        result = conn.execute(
            """
            WITH symbol_stats AS (SELECT symbol, COUNT(*) as bar_count,
                MAX(date) as latest_date, CURRENT_DATE - MAX(date) as days_since_latest
                FROM day_bars WHERE symbol = ANY(?::text[]) GROUP BY symbol)
            SELECT symbol FROM UNNEST(?::text[]) as t(symbol) LEFT JOIN symbol_stats USING (symbol)
            WHERE symbol_stats.symbol IS NULL OR bar_count < ? OR days_since_latest > ?
            """,
            [symbols, symbols, min_days, stale_threshold_days],
        ).fetchall()
        symbols_needing_backfill = [str(row[0]) for row in result]
    if symbols_needing_backfill:
        logger.info("detected_symbols_needing_backfill", count=len(symbols_needing_backfill),
                    symbols=symbols_needing_backfill, min_days=min_days,
                    stale_threshold_days=stale_threshold_days)
    return symbols_needing_backfill


def _enrich_news_sentiment(storage: PortfolioStorage, symbol: str, fund: FundamentalData) -> None:
    """Attach news sentiment score to fundamentals in-place."""
    try:
        ns = get_symbol_sentiment(storage, symbol)
        if ns.sentiment_score is not None:
            fund.news_sentiment_score = ns.sentiment_score
    except Exception as e:
        logger.debug("news_sentiment_fetch_skipped", symbol=symbol, error=str(e))


def _score_and_classify(conn, storage: PortfolioStorage, symbol: str) -> tuple[FundamentalData | None, str | None]:
    """Fetch, score, and classify fundamentals; returns (data, health)."""
    try:
        fund = fetch_fundamentals_cached(conn, symbol, ttl_days=1)
        if not fund:
            return None, None
        _enrich_news_sentiment(storage, symbol, fund)
        fund.valuation_score = calculate_valuation_score(fund)
        fund.growth_score = calculate_growth_score(fund)
        fund.health_score = calculate_health_score(fund)
        fund.sentiment_score = calculate_sentiment_score(fund)
        fund.fundamental_score = calculate_fundamental_score(fund)
        return fund, classify_company_health(fund)
    except Exception as e:
        logger.warning("fundamentals_fetch_failed", symbol=symbol, error=str(e))
        return None, None


def _fetch_earnings_info(conn, symbol: str, now: datetime) -> tuple[datetime | None, int | None]:
    """Fetch earnings date; returns (date, days_away) or (None, None)."""
    try:
        ed = fetch_earnings_date_cached(conn, symbol, ttl_days=30)
        if ed:
            d = (ed.date() - now.date()).days
            return ed, d if d >= 0 else None
        return None, None
    except Exception as e:
        logger.warning("earnings_fetch_failed", symbol=symbol, error=str(e))
        return None, None


def fetch_fundamentals_and_earnings(
    storage: PortfolioStorage,
    symbol: str,
    now: datetime,
) -> tuple[FundamentalData | None, str | None, datetime | None, int | None]:
    """Fetch fundamental data and earnings info; returns (data, health, date, days_away)."""
    with storage.connection() as conn:
        fund, health = _score_and_classify(conn, storage, symbol)
        ed, days = _fetch_earnings_info(conn, symbol, now)
    return fund, health, ed, days


def fetch_auxiliary_data(
    storage: PortfolioStorage,
    news_service: NewsService,
    symbol: str,
    max_news_articles: int,
    news_bundle: NewsBundle | None,
) -> tuple[float | None, float | None, float | None, float | None, NewsBundle | None]:
    """Fetch volume, SMA5, news sentiment; returns (current_vol, avg_vol_20d, sma5_prev, news_score, bundle)."""
    vdf = storage.query(
        "SELECT volume FROM day_bars WHERE symbol = ? ORDER BY date DESC LIMIT 20", [symbol]
    )
    current_volume = avg_volume_20d = None
    if vdf.height > 0:
        vols = [v for v in vdf["volume"].to_list() if v is not None]
        current_volume = float(vols[0]) if vols else None
        if vdf.height >= 20 and vols:
            avg_volume_20d = sum(vols) / len(vols)
        else:
            logger.debug("insufficient_volume_history", symbol=symbol, days_available=vdf.height,
                         message="Less than 20 days of volume data - skipping 20-day average")

    with storage.connection() as conn:
        prev_date = (datetime.now(UTC) - timedelta(days=1)).date()
        result = conn.execute(
            "SELECT sma_5 FROM technical_indicators WHERE symbol = %s AND DATE(calculated_at) = %s"
            " ORDER BY calculated_at DESC LIMIT 1",
            (symbol, str(prev_date)),
        ).fetchone()
    sma_5_prev = float(result[0]) if result and result[0] is not None else None

    news_sentiment_value: float | None = None
    try:
        if news_bundle is None:
            news_bundle = news_service.get_news_intelligence(symbol, max_articles=max_news_articles)
        news_sentiment_value = news_bundle.summary.score
    except Exception as exc:  # pragma: no cover - downstream services may fail
        logger.warning("news_fetch_failed", symbol=symbol, error=str(exc))

    return current_volume, avg_volume_20d, sma_5_prev, news_sentiment_value, news_bundle


def fetch_strategy_sharpe(storage: PortfolioStorage, symbol: str) -> float | None:
    """Fetch 30-day rolling Sharpe from active strategy for symbol (auto-002)."""
    try:
        with storage.connection() as conn:
            result = conn.execute(
                "SELECT sp.sharpe_ratio_30d FROM strategy_definitions sd"
                " JOIN strategy_performance sp ON sd.id = sp.strategy_id"
                " WHERE sd.symbol = %s AND sd.status = 'active'"
                " ORDER BY sp.date DESC LIMIT 1",
                (symbol,),
            ).fetchone()
        if result and result[0] is not None:
            sharpe = float(result[0])
            logger.debug("strategy_sharpe_fetched", symbol=symbol, sharpe_30d=sharpe)
            return sharpe
        return None
    except Exception as e:
        logger.warning("strategy_sharpe_fetch_failed", symbol=symbol, error=str(e))
        return None

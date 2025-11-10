"""Per-ticker processing logic for watchlist refresh.

This module handles the per-ticker data gathering and snapshot creation
during watchlist refresh operations.

Extracted from scoring_service.py to reduce file size and improve modularity.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict, cast

from ..logging_config import get_logger
from ..portfolio.models import PriceData
from ..services import NewsService
from ..services.news_models import NewsArticle, NewsBundle
from ..storage import PortfolioStorage
from ..utils.market_hours import is_stale
from .calculator import (
    calculate_entry_price,
    calculate_position_size,
    calculate_profit_target,
    calculate_stop_loss,
)
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
from .models import (
    ScoreWeights,
    SignalType,
    TechnicalSnapshot,
    WatchlistScoreInputs,
    WatchlistSnapshot,
)
from .narrative import (
    classify_signal,
    classify_trading_style,
    generate_action_plan,
    generate_company_health_bullets,
    generate_headline,
    generate_position_sizing_text,
    generate_special_notes,
)
from .scoring import calculate_watchlist_scores

logger = get_logger(__name__)

WATCHLIST_NEWS_ARTICLE_LIMIT = 5


class TradingStyleDict(TypedDict):
    """Trading style classification result."""

    style: str
    confidence: int
    holding_period: str
    risk_level: str


class NarrativeResultDict(TypedDict):
    """Result from _generate_narrative_and_trade_levels function."""

    signal_type: str
    signal_strength: int
    headline: str
    style_result: TradingStyleDict
    entry_price: float | None
    stop_loss: float | None
    profit_target: float | None
    position_size: int | None
    action_plan: str | None
    position_sizing: str | None
    company_health_bullets: list[str] | None
    special_notes: str | None


def _normalize_publisher_field(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("title", "name"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    elif isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _get_article_attr(article: NewsArticle | Mapping[str, Any], field: str) -> Any:
    if isinstance(article, dict):
        return article.get(field)
    return getattr(article, field, None)


def _extract_article_vendor(article: NewsArticle | Mapping[str, Any]) -> str | None:
    vendor = _get_article_attr(article, "vendor")
    if isinstance(vendor, str) and vendor.strip():
        return vendor.strip()

    raw_payload = _get_article_attr(article, "raw") or {}
    fallback_vendor = raw_payload.get("vendor")
    if isinstance(fallback_vendor, str) and fallback_vendor.strip():
        return fallback_vendor.strip()

    inner_raw = raw_payload.get("raw")
    if isinstance(inner_raw, dict):
        nested_vendor = inner_raw.get("vendor")
        if isinstance(nested_vendor, str) and nested_vendor.strip():
            return nested_vendor.strip()

    return None


def _extract_article_publisher(article: NewsArticle | Mapping[str, Any]) -> str | None:
    publisher = _get_article_attr(article, "source")
    if isinstance(publisher, str) and publisher.strip():
        return publisher.strip()

    raw_payload = _get_article_attr(article, "raw") or {}
    for key in ("news_source_name", "source"):
        candidate = _normalize_publisher_field(raw_payload.get(key))
        if candidate:
            return candidate

    inner_raw = raw_payload.get("raw")
    if isinstance(inner_raw, dict):
        for key in ("news_source_name", "source"):
            candidate = _normalize_publisher_field(inner_raw.get(key))
            if candidate:
                return candidate

    return None


def build_recent_news_payload(
    news_bundle: NewsBundle,
    *,
    max_articles: int = WATCHLIST_NEWS_ARTICLE_LIMIT,
) -> dict[str, Any]:
    """Serialize recent news bundle for watchlist snapshots."""

    articles_payload: list[dict[str, Any]] = []
    for article in news_bundle.articles[:max_articles]:
        article_payload = article.model_dump(mode="json")

        vendor = _extract_article_vendor(article)
        if vendor:
            article_payload["vendor"] = vendor
        elif "vendor" not in article_payload:
            article_payload["vendor"] = None

        publisher = _extract_article_publisher(article)
        if publisher:
            article_payload["source"] = publisher
        elif not article_payload.get("source"):
            article_payload["source"] = None

        # Explicit publisher alias to simplify UI rendering logic
        article_payload.setdefault("publisher", article_payload.get("source"))

        articles_payload.append(article_payload)

    return {
        "summary": news_bundle.summary.model_dump(mode="json"),
        "articles": articles_payload,
    }


def calculate_price_change(
    storage: PortfolioStorage, symbol: str, price: float | None, item_id: str | None = None
) -> tuple[float | None, bool]:
    """Calculate price change percentage for a symbol.

    First tries to calculate from day_bars historical data (preferred).
    Falls back to previous watchlist snapshot if available.

    Args:
        storage: PortfolioStorage instance
        symbol: Ticker symbol
        price: Current price
        item_id: Watchlist item ID (for snapshot fallback)

    Returns:
        Tuple of (change_pct, has_historical_data):
        - change_pct: Price change percentage or None if insufficient data
        - has_historical_data: True if day_bars data exists (False triggers backfill)
    """
    if price is None or price <= 0:
        return (None, False)

    # Try day_bars historical data first (preferred)
    df = storage.query(
        """
        SELECT close
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 2
        """,
        [symbol],
    )
    if df.height >= 2:
        prev_close = df["close"][1]
        if prev_close not in (0, None):
            return (float((price - prev_close) / prev_close * 100.0), True)

    # Fallback: Use previous watchlist snapshot if available
    if item_id:
        snapshot_df = storage.query(
            """
            SELECT price
            FROM watchlist_snapshots
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )
        if snapshot_df.height > 0:
            prev_price = snapshot_df["price"][0]
            if prev_price and prev_price > 0:
                # Using snapshot fallback means no historical data
                return (float((price - prev_price) / prev_price * 100.0), False)

    # No data available for comparison
    return (None, False)


def detect_missing_historical_data(
    storage: PortfolioStorage,
    symbols: list[str],
    min_days: int = 30,
    stale_threshold_days: int = 7,
) -> list[str]:
    """Detect tickers that need historical data backfill.

    Checks day_bars table to find tickers with:
    - No historical data at all
    - Insufficient data (< min_days of trading days)
    - Stale data (most recent bar > stale_threshold_days old)

    Args:
        storage: Database storage instance
        symbols: List of ticker symbols to check
        min_days: Minimum number of trading days required (default: 30)
        stale_threshold_days: Days threshold to consider data stale (default: 7)

    Returns:
        List of ticker symbols that need backfill
    """
    if not symbols:
        return []

    with storage.connection() as conn:
        # Check each ticker's historical data status
        query = """
            WITH ticker_stats AS (
                SELECT
                    ticker,
                    COUNT(*) as bar_count,
                    MAX(date) as latest_date,
                    CURRENT_DATE - MAX(date) as days_since_latest
                FROM day_bars
                WHERE ticker = ANY(?)
                GROUP BY ticker
            )
            SELECT ticker
            FROM UNNEST(?) as t(ticker)
            LEFT JOIN ticker_stats USING (ticker)
            WHERE
                ticker_stats.ticker IS NULL  -- No data at all
                OR bar_count < ?  -- Insufficient data
                OR days_since_latest > ?  -- Stale data
        """

        result = conn.execute(
            query,
            [symbols, symbols, min_days, stale_threshold_days],
        ).fetchall()

        tickers_needing_backfill = [row[0] for row in result]

        if tickers_needing_backfill:
            logger.info(
                "detected_tickers_needing_backfill",
                count=len(tickers_needing_backfill),
                tickers=tickers_needing_backfill,
                min_days=min_days,
                stale_threshold_days=stale_threshold_days,
            )

        return tickers_needing_backfill


def _fetch_fundamentals_and_earnings(
    storage: PortfolioStorage,
    symbol: str,
    now: datetime,
) -> tuple[FundamentalData | None, str | None, datetime | None, int | None]:
    """Fetch fundamental data and earnings information for a symbol.

    Returns:
        Tuple of (fundamentals_data, company_health, earnings_date, earnings_days_away)
    """
    fundamentals_data = None
    company_health_str: str | None = None
    earnings_date_obj: datetime | None = None
    earnings_days_away_val: int | None = None

    with storage.connection() as conn:
        # Fetch fundamentals (cached 24 hours)
        try:
            fundamentals_data = fetch_fundamentals_cached(conn, symbol, ttl_days=1)
            if fundamentals_data:
                # Calculate 4-pillar fundamental scores
                fundamentals_data.valuation_score = calculate_valuation_score(fundamentals_data)
                fundamentals_data.growth_score = calculate_growth_score(fundamentals_data)
                fundamentals_data.health_score = calculate_health_score(fundamentals_data)
                fundamentals_data.sentiment_score = calculate_sentiment_score(fundamentals_data)
                fundamentals_data.fundamental_score = calculate_fundamental_score(fundamentals_data)
                company_health_str = classify_company_health(fundamentals_data)
        except Exception as fundamentals_error:
            logger.warning(
                "fundamentals_fetch_failed",
                symbol=symbol,
                error=str(fundamentals_error),
            )

        # Fetch earnings date (cached 30 days)
        try:
            earnings_date_obj = fetch_earnings_date_cached(conn, symbol, ttl_days=30)
            if earnings_date_obj:
                # Calculate days until earnings
                days_diff = (earnings_date_obj.date() - now.date()).days
                earnings_days_away_val = days_diff if days_diff >= 0 else None
        except Exception as earnings_error:
            logger.warning(
                "earnings_fetch_failed",
                symbol=symbol,
                error=str(earnings_error),
            )

    return fundamentals_data, company_health_str, earnings_date_obj, earnings_days_away_val


def _fetch_volume_data(
    storage: PortfolioStorage,
    symbol: str,
) -> tuple[float | None, float | None]:
    """Fetch current volume and 20-day average from day_bars.

    Returns:
        Tuple of (current_volume, avg_volume_20d)
    """
    current_volume: float | None = None
    avg_volume_20d: float | None = None

    volume_df = storage.query(
        """
        SELECT volume
        FROM day_bars
        WHERE ticker = ?
        ORDER BY date DESC
        LIMIT 20
        """,
        [symbol],
    )

    if volume_df.height >= 20:
        volumes = volume_df["volume"].to_list()
        current_volume = float(volumes[0]) if volumes[0] is not None else None
        avg_volume_20d = sum(v for v in volumes if v is not None) / len(
            [v for v in volumes if v is not None]
        )
    elif volume_df.height > 0:
        # Less than 20 days available - use what we have
        volumes = volume_df["volume"].to_list()
        current_volume = float(volumes[0]) if volumes[0] is not None else None
        logger.debug(
            "insufficient_volume_history",
            symbol=symbol,
            days_available=volume_df.height,
            message="Less than 20 days of volume data - skipping 20-day average",
        )

    return current_volume, avg_volume_20d


def _fetch_previous_sma5(
    storage: PortfolioStorage,
    symbol: str,
) -> float | None:
    """Fetch previous day's SMA_5 from technical indicators."""
    with storage.connection() as conn:
        prev_date = (datetime.now(UTC) - timedelta(days=1)).date()
        sma_5_prev_query = """
            SELECT sma_5 FROM technical_indicators
            WHERE ticker = %s AND DATE(calculated_at) = %s
            ORDER BY calculated_at DESC LIMIT 1
        """
        result = conn.execute(sma_5_prev_query, (symbol, prev_date)).fetchone()
        return result[0] if result else None


def _fetch_news_sentiment(
    news_service: NewsService,
    symbol: str,
    max_news_articles: int,
    news_bundle: NewsBundle | None = None,
) -> tuple[float | None, dict[str, object] | None]:
    """Fetch news sentiment score and recent headlines.

    Returns:
        Tuple of (news_sentiment_score, recent_news_payload)
    """
    news_sentiment_value: float | None = None
    recent_news_value: dict[str, object] | None = None

    try:
        if news_bundle is None:
            # Fallback: Individual fetch (backwards compatibility)
            news_bundle = news_service.get_symbol_news(symbol, max_articles=max_news_articles)

        news_sentiment_value = news_bundle.summary.score
        recent_news_value = build_recent_news_payload(
            news_bundle, max_articles=WATCHLIST_NEWS_ARTICLE_LIMIT
        )
    except Exception as exc:  # pragma: no cover - downstream services may fail
        logger.warning("news_fetch_failed", symbol=symbol, error=str(exc))

    return news_sentiment_value, recent_news_value


def _build_signal_inputs(
    price_data: PriceData,
    technical_snapshot: TechnicalSnapshot,
    current_volume: float | None,
    avg_volume_20d: float | None,
    sma_5_prev: float | None,
    company_health_str: str | None,
    news_sentiment_value: float | None,
    earnings_days_away_val: int | None,
) -> dict[str, Any]:
    """Build signal inputs for classification."""
    return {
        "price": price_data.price,
        "ema_20": technical_snapshot.ema_20,
        "sma_5": technical_snapshot.sma_5,
        "sma_5_prev": sma_5_prev,
        "rsi_14": technical_snapshot.rsi_14,
        "macd": technical_snapshot.macd,
        "volume": current_volume,
        "volume_avg_20d": avg_volume_20d,
        "company_health": company_health_str,
        "news_sentiment": news_sentiment_value,
        "earnings_days_away": earnings_days_away_val,
    }


def _calculate_trade_levels(
    storage: PortfolioStorage,
    symbol: str,
    price: float | None,
    signal_type: str,
    risk_budget: float,
) -> tuple[float | None, float | None, float | None, int | None]:
    """Calculate entry price, stop loss, profit target, and position size.

    Returns:
        Tuple of (entry_price, stop_loss, profit_target, position_size)
    """
    if price is None:
        return None, None, None, None

    entry_price = calculate_entry_price(price, signal_type)
    if entry_price is None:
        return None, None, None, None

    with storage.connection() as conn:
        stop_loss = calculate_stop_loss(conn, symbol, entry_price)
        profit_target = calculate_profit_target(conn, symbol, entry_price)

    if stop_loss is None:
        return entry_price, None, None, None

    position_size = calculate_position_size(
        entry_price=entry_price,
        stop_loss=stop_loss,
        risk_budget=risk_budget,
    )

    return entry_price, stop_loss, profit_target, position_size


def _generate_narrative_texts(
    symbol: str,
    signal_type: str,
    signal_strength: int,
    entry_price: float | None,
    stop_loss: float | None,
    profit_target: float | None,
    position_size: int | None,
    company_health_str: str | None,
    earnings_days_away: int | None,
    fundamentals_data: FundamentalData | None,
) -> tuple[str | None, str | None, list[str] | None, str | None]:
    """Generate all narrative text components.

    Returns:
        Tuple of (action_plan, position_sizing, company_health_bullets, special_notes)
    """
    action_plan = None
    position_sizing = None
    company_health_bullets = None
    special_notes = None

    # Action plan
    if entry_price is not None and stop_loss is not None and profit_target is not None:
        try:
            action_plan = generate_action_plan(
                signal_type=signal_type,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target,
            )
        except Exception as e:
            logger.warning("action_plan_generation_failed", symbol=symbol, error=str(e))

    # Position sizing text
    if (
        position_size is not None
        and entry_price is not None
        and profit_target is not None
        and stop_loss is not None
    ):
        try:
            position_sizing = generate_position_sizing_text(
                shares=position_size,
                entry_price=entry_price,
                stop_loss=stop_loss,
                profit_target=profit_target,
            )
        except Exception as e:
            logger.warning("position_sizing_text_generation_failed", symbol=symbol, error=str(e))

    # Company health bullets
    if fundamentals_data is not None:
        try:
            fundamentals_dict = {
                "revenue_growth": fundamentals_data.revenue_growth,
                "profit_margin": fundamentals_data.profit_margin,
                "debt_to_equity": fundamentals_data.debt_to_equity,
                "cash": None,
                "analyst_buy_pct": None,
            }

            if fundamentals_data.recommendation_mean is not None:
                analyst_buy_pct = (5.0 - fundamentals_data.recommendation_mean) / 4.0
                fundamentals_dict["analyst_buy_pct"] = max(0.0, min(1.0, analyst_buy_pct))

            company_health_bullets = generate_company_health_bullets(fundamentals_dict)
        except Exception as e:
            logger.warning("company_health_bullets_generation_failed", symbol=symbol, error=str(e))

    # Special notes
    if company_health_str is not None:
        try:
            special_notes = generate_special_notes(
                signal_type=signal_type,
                signal_strength=signal_strength,
                earnings_days_away=earnings_days_away,
                company_health=company_health_str,
            )
        except Exception as e:
            logger.warning("special_notes_generation_failed", symbol=symbol, error=str(e))

    return action_plan, position_sizing, company_health_bullets, special_notes


def _classify_signal_and_style(
    symbol: str,
    signal_inputs: dict[str, Any],
    rsi_14: float | None,
    earnings_days_away: int | None,
) -> tuple[str, int, str, TradingStyleDict]:
    """Classify trading signal and style.

    Returns:
        Tuple of (signal_type, signal_strength, headline, style_result)
    """
    classification = classify_signal(signal_inputs)
    signal_type_str = classification.signal_type.value
    signal_strength_val = classification.strength.value
    headline = generate_headline(classification)

    style_result = cast(
        TradingStyleDict,
        classify_trading_style(
            symbol=symbol,
            signal_strength=signal_strength_val,
            signal_type=signal_type_str,
            rsi_14=rsi_14 or 50.0,
            earnings_days_away=earnings_days_away,
        ),
    )

    return signal_type_str, signal_strength_val, headline, style_result


def _build_narrative_result(
    signal_type: str,
    signal_strength: int,
    headline: str,
    style_result: TradingStyleDict,
    entry_price: float | None,
    stop_loss: float | None,
    profit_target: float | None,
    position_size: int | None,
    action_plan: str | None,
    position_sizing: str | None,
    company_health_bullets: list[str] | None,
    special_notes: str | None,
) -> NarrativeResultDict:
    """Build narrative result dictionary from components."""
    return {
        "signal_type": signal_type,
        "signal_strength": signal_strength,
        "headline": headline,
        "style_result": style_result,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "profit_target": profit_target,
        "position_size": position_size,
        "action_plan": action_plan,
        "position_sizing": position_sizing,
        "company_health_bullets": company_health_bullets,
        "special_notes": special_notes,
    }


def _create_default_narrative_result(symbol: str) -> NarrativeResultDict:
    """Create default narrative result when generation fails."""
    return _build_narrative_result(
        signal_type=SignalType.HOLD.value,
        signal_strength=5,
        headline=f"HOLD - {symbol}",
        style_result=cast(
            TradingStyleDict,
            {
                "style": "Value",
                "confidence": 5,
                "holding_period": "Unknown",
                "risk_level": "Medium",
            },
        ),
        entry_price=None,
        stop_loss=None,
        profit_target=None,
        position_size=None,
        action_plan=None,
        position_sizing=None,
        company_health_bullets=None,
        special_notes=None,
    )


def _generate_narrative_and_trade_levels(
    storage: PortfolioStorage,
    symbol: str,
    price_data: PriceData,
    technical_snapshot: TechnicalSnapshot,
    current_volume: float | None,
    avg_volume_20d: float | None,
    sma_5_prev: float | None,
    company_health_str: str | None,
    news_sentiment_value: float | None,
    earnings_days_away_val: int | None,
    fundamentals_data: FundamentalData | None,
    risk_budget: float,
) -> NarrativeResultDict:
    """Generate narrative intelligence and calculate trade levels.

    Returns:
        Dict with all narrative and trade calculation results
    """
    try:
        signal_inputs = _build_signal_inputs(
            price_data,
            technical_snapshot,
            current_volume,
            avg_volume_20d,
            sma_5_prev,
            company_health_str,
            news_sentiment_value,
            earnings_days_away_val,
        )
        signal_type, signal_strength, headline, style_result = _classify_signal_and_style(
            symbol, signal_inputs, technical_snapshot.rsi_14, earnings_days_away_val
        )
        entry_price, stop_loss, profit_target, position_size = _calculate_trade_levels(
            storage, symbol, price_data.price, signal_type, risk_budget
        )
        action_plan, position_sizing, company_health_bullets, special_notes = (
            _generate_narrative_texts(
                symbol,
                signal_type,
                signal_strength,
                entry_price,
                stop_loss,
                profit_target,
                position_size,
                company_health_str,
                earnings_days_away_val,
                fundamentals_data,
            )
        )
        return _build_narrative_result(
            signal_type,
            signal_strength,
            headline,
            style_result,
            entry_price,
            stop_loss,
            profit_target,
            position_size,
            action_plan,
            position_sizing,
            company_health_bullets,
            special_notes,
        )
    except Exception as e:
        logger.warning("narrative_generation_failed", symbol=symbol, error=str(e))
        return _create_default_narrative_result(symbol)


def _handle_price_change_and_backfill(
    storage: PortfolioStorage,
    symbol: str,
    price: float,
    item_id: str,
) -> float:
    """Calculate price change and queue backfill if needed.

    Returns:
        Price change percentage (defaults to 0.0 if no historical data)
    """
    change_pct, has_historical_data = calculate_price_change(storage, symbol, price, item_id)

    # Queue backfill task if historical data is missing
    if not has_historical_data:
        try:
            from ..tasks.data_ingestion_tasks import (  # noqa: PLC0415 - avoid circular dependency
                ingest_historical_ohlcv,
            )

            # Queue backfill for 252 trading days (~1 year)
            ingest_historical_ohlcv.delay([symbol], days=252)
            logger.info(
                "watchlist_refresh_queued_backfill",
                symbol=symbol,
                item_id=item_id,
                reason="Missing day_bars data - queued historical backfill task",
            )
        except Exception as e:
            logger.warning(
                "watchlist_refresh_backfill_queue_failed",
                symbol=symbol,
                item_id=item_id,
                error=str(e),
            )

    # Default to 0.0% change if no comparison data available
    if change_pct is None:
        logger.info(
            "watchlist_refresh_defaulted_change_pct",
            symbol=symbol,
            item_id=item_id,
            change_pct=0.0,
            reason="No comparison data (first snapshot) - defaulting to 0.0%",
        )
        change_pct = 0.0

    return change_pct


def _prepare_technical_snapshot(
    technical_map: dict[str, TechnicalSnapshot],
    symbol: str,
    price: float,
) -> TechnicalSnapshot:
    """Get technical snapshot and set current price.

    Returns:
        TechnicalSnapshot with current price set
    """
    technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
    technical_snapshot.price = price
    return technical_snapshot


def _fetch_auxiliary_data(
    storage: PortfolioStorage,
    news_service: NewsService,
    symbol: str,
    max_news_articles: int,
    news_bundle: NewsBundle | None,
) -> tuple[float | None, float | None, float | None, float | None, dict[str, object] | None]:
    """Fetch auxiliary data: volume, SMA5, news sentiment.

    Returns:
        Tuple of (current_volume, avg_volume_20d, sma_5_prev, news_sentiment, recent_news)
    """
    # Query volume data from day_bars (latest + 20-day average)
    current_volume, avg_volume_20d = _fetch_volume_data(storage, symbol)

    # Query previous day's SMA_5
    sma_5_prev = _fetch_previous_sma5(storage, symbol)

    # Fetch sentiment-scored news bundle
    news_sentiment_value, recent_news_value = _fetch_news_sentiment(
        news_service, symbol, max_news_articles, news_bundle
    )

    return current_volume, avg_volume_20d, sma_5_prev, news_sentiment_value, recent_news_value


def _build_watchlist_snapshot(
    item_id: str,
    now: datetime,
    price_data: PriceData,
    change_pct: float,
    breakdown: Any,
    narrative_result: NarrativeResultDict,
    company_health_str: str | None,
    earnings_date_obj: datetime | None,
    earnings_days_away_val: int | None,
    news_sentiment_value: float | None,
    recent_news_value: dict[str, object] | None,
) -> WatchlistSnapshot:
    """Build final WatchlistSnapshot from all processed data.

    Args:
        item_id: Watchlist item ID
        now: Current timestamp
        price_data: Price data object
        change_pct: Price change percentage
        breakdown: Score breakdown object
        narrative_result: Dict with narrative/trade results
        company_health_str: Company health classification
        earnings_date_obj: Earnings date
        earnings_days_away_val: Days until earnings
        news_sentiment_value: News sentiment score
        recent_news_value: Recent news payload

    Returns:
        Complete WatchlistSnapshot ready to persist
    """
    # Calculate staleness
    data_is_stale = is_stale(fetched_at=now, now=now)

    # Create snapshot
    snapshot = WatchlistSnapshot(
        item_id=item_id,
        fetched_at=now,
        price=price_data.price,
        change_pct=change_pct,
        beta=price_data.beta,
        volatility=price_data.volatility,
        overall_score=breakdown.overall,
        technical_score=breakdown.technical.score,
        fundamental_score=breakdown.fundamental.score if breakdown.fundamental else None,
        is_stale=data_is_stale,
        raw_metrics=breakdown.to_snapshot_payload(),
        # Narrative fields
        signal_type=narrative_result["signal_type"],
        signal_strength=narrative_result["signal_strength"],
        narrative_headline=narrative_result["headline"],
        recommended_style=narrative_result["style_result"]["style"],
        style_confidence=narrative_result["style_result"]["confidence"],
        optimal_holding_period=narrative_result["style_result"]["holding_period"],
        risk_level=narrative_result["style_result"]["risk_level"],
        # Trade calculation fields
        entry_price=narrative_result["entry_price"],
        stop_loss=narrative_result["stop_loss"],
        profit_target=narrative_result["profit_target"],
        position_size_shares=narrative_result["position_size"],
        # Narrative text fields
        narrative_action_plan=narrative_result["action_plan"],
        narrative_position_sizing=narrative_result["position_sizing"],
        narrative_company_health={"bullets": narrative_result["company_health_bullets"]}
        if narrative_result["company_health_bullets"]
        else None,
        narrative_special_notes=narrative_result["special_notes"],
        # Fundamental/earnings fields
        company_health=company_health_str,
        earnings_date=earnings_date_obj,
        earnings_days_away=earnings_days_away_val,
        # News/sentiment fields
        news_sentiment_score=news_sentiment_value,
        recent_news_headlines=recent_news_value,
    )

    return snapshot


def process_ticker_snapshot(
    storage: PortfolioStorage,
    symbol: str,
    item_id: str,
    price_data: PriceData,
    technical_map: dict[str, TechnicalSnapshot],
    default_weights: ScoreWeights,
    stale_ttl_minutes: int,
    risk_budget: float,
    now: datetime,
    news_service: NewsService,
    max_news_articles: int,
    news_bundle: NewsBundle | None = None,
) -> WatchlistSnapshot:
    """Process a single ticker and generate its watchlist snapshot.

    This function consolidates all data gathering, calculation, and narrative
    generation for one ticker into a single snapshot.

    Args:
        storage: Database storage instance
        symbol: Ticker symbol
        item_id: Watchlist item ID
        price_data: Price data object (from PriceDataFetcher)
        technical_map: Map of symbol -> TechnicalSnapshot
        default_weights: Score weights from preferences
        stale_ttl_minutes: Staleness threshold in minutes
        risk_budget: Risk budget for position sizing
        now: Current timestamp (UTC)
        news_service: NewsService instance for fetching scored news
        max_news_articles: Maximum articles to fetch (if news_bundle not provided)
        news_bundle: Optional pre-fetched NewsBundle (Issue #2 fix - batch fetching)

    Returns:
        WatchlistSnapshot ready to be persisted

    Raises:
        Exception: If processing fails (caller should catch and log)
    """
    # Calculate price change and queue backfill if needed
    change_pct = _handle_price_change_and_backfill(storage, symbol, price_data.price, item_id)

    # Get technical snapshot with current price
    technical_snapshot = _prepare_technical_snapshot(technical_map, symbol, price_data.price)

    # Fetch fundamentals and earnings data (needed for both scoring and narrative)
    (
        fundamentals_data,
        company_health_str,
        earnings_date_obj,
        earnings_days_away_val,
    ) = _fetch_fundamentals_and_earnings(storage, symbol, now)

    # Calculate scores (3-pillar: price/technical/fundamental)
    breakdown = calculate_watchlist_scores(
        WatchlistScoreInputs(
            price=price_data,
            price_change_pct=change_pct,
            technical=technical_snapshot,
            fundamental=fundamentals_data,
            weights=default_weights,
            now=now,
            stale_ttl_minutes=stale_ttl_minutes,
        )
    )

    # Fetch auxiliary data: volume, SMA5, news
    current_volume, avg_volume_20d, sma_5_prev, news_sentiment_value, recent_news_value = (
        _fetch_auxiliary_data(storage, news_service, symbol, max_news_articles, news_bundle)
    )

    # Generate narrative intelligence and calculate trade levels
    narrative_result = _generate_narrative_and_trade_levels(
        storage=storage,
        symbol=symbol,
        price_data=price_data,
        technical_snapshot=technical_snapshot,
        current_volume=current_volume,
        avg_volume_20d=avg_volume_20d,
        sma_5_prev=sma_5_prev,
        company_health_str=company_health_str,
        news_sentiment_value=news_sentiment_value,
        earnings_days_away_val=earnings_days_away_val,
        fundamentals_data=fundamentals_data,
        risk_budget=risk_budget,
    )

    # Build and return final snapshot
    return _build_watchlist_snapshot(
        item_id=item_id,
        now=now,
        price_data=price_data,
        change_pct=change_pct,
        breakdown=breakdown,
        narrative_result=narrative_result,
        company_health_str=company_health_str,
        earnings_date_obj=earnings_date_obj,
        earnings_days_away_val=earnings_days_away_val,
        news_sentiment_value=news_sentiment_value,
        recent_news_value=recent_news_value,
    )

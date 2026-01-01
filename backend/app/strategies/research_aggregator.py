"""Research aggregation service for dynamic strategy generation.

This module collects and structures market research from all available sources:
- News sentiment (30-day rolling analysis)
- Fundamental metrics (company health, valuation, growth)
- Technical indicators (trend, momentum, volume)
- Macro context (Fear & Greed, market regime)
- Sector relative strength (vs SPY benchmark)

Output: ResearchInsights dataclass with confidence scores for each dimension.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Literal

from app.analytics.indicators import calculate_indicators_for_symbol
from app.storage import PortfolioStorage
from app.watchlist.fundamentals import (
    FundamentalData,
    calculate_fundamental_score,
    classify_company_health,
    fetch_fundamentals,
)

from .models import ResearchInsights

logger = logging.getLogger(__name__)


# Material event keywords for headline classification
MATERIAL_EVENT_KEYWORDS: dict[str, list[str]] = {
    "earnings": ["earnings", "beat", "miss", "eps", "revenue"],
    "product_launch": ["product", "launch", "release", "announce"],
    "acquisition": ["acquisition", "merger", "acquire", "buyout"],
    "regulatory": ["fda", "approval", "regulatory", "sec"],
}

# News volume thresholds for confidence calculation
NEWS_CONFIDENCE_THRESHOLDS: dict[int, float] = {
    20: 1.0,
    10: 0.8,
    5: 0.6,
}
NEWS_CONFIDENCE_DEFAULT = 0.4


def _extract_material_events(news_rows: list[dict[str, Any]]) -> list[str]:
    """Extract material events from headlines using keyword classification.

    Args:
        news_rows: List of news article dicts with 'headline' key

    Returns:
        List of unique event types found (e.g., ['earnings', 'acquisition'])
    """
    material_events = []
    for row in news_rows:
        headline = row.get("headline", "")
        if not headline:
            continue
        headline_lower = headline.lower()
        for event_type, keywords in MATERIAL_EVENT_KEYWORDS.items():
            if any(kw in headline_lower for kw in keywords):
                material_events.append(event_type)
                break  # One event type per headline
    return list(set(material_events))


def _calculate_news_confidence(news_volume: int) -> float:
    """Calculate confidence score based on article count.

    Args:
        news_volume: Number of news articles

    Returns:
        Confidence score between 0.0 and 1.0
    """
    for threshold, confidence in sorted(NEWS_CONFIDENCE_THRESHOLDS.items(), reverse=True):
        if news_volume >= threshold:
            return confidence
    return NEWS_CONFIDENCE_DEFAULT


def _classify_trend_strength(
    price: float, sma_20: float, sma_50: float, sma_200: float
) -> Literal["strong_up", "weak_up", "neutral", "weak_down", "strong_down"]:
    """Classify trend strength based on price vs moving averages.

    Args:
        price: Current stock price
        sma_20: 20-day simple moving average
        sma_50: 50-day simple moving average
        sma_200: 200-day simple moving average

    Returns:
        Trend strength classification
    """
    if price > sma_20 and price > sma_50 and price > sma_200:
        if sma_200 > 0 and price / sma_200 > 1.10:
            return "strong_up"
        return "weak_up"
    if price < sma_20 and price < sma_50 and price < sma_200:
        if sma_200 > 0 and price / sma_200 < 0.90:
            return "strong_down"
        return "weak_down"
    return "neutral"


def _analyze_momentum(
    macd_data: dict[str, Any] | float,
) -> Literal["accelerating", "steady", "decelerating"]:
    """Classify momentum using MACD histogram.

    Args:
        macd_data: MACD data dict with 'histogram' key, or float

    Returns:
        Momentum classification
    """
    macd_hist = macd_data.get("histogram", 0.0) if isinstance(macd_data, dict) else 0.0
    if macd_hist > 1.0:
        return "accelerating"
    if macd_hist < -1.0:
        return "decelerating"
    return "steady"


def _classify_rsi_zone(rsi_14: float) -> Literal["oversold", "healthy", "overbought"]:
    """Classify RSI zone.

    Args:
        rsi_14: 14-period RSI value

    Returns:
        RSI zone classification
    """
    if rsi_14 < 30:
        return "oversold"
    if rsi_14 > 70:
        return "overbought"
    return "healthy"


class ResearchAggregationService:
    """Service for aggregating market research from multiple sources."""

    def __init__(self) -> None:
        """Initialize research aggregation service."""
        self.storage = PortfolioStorage()

    async def aggregate_research(self, symbol: str, lookback_days: int = 30) -> ResearchInsights:
        """Aggregate market research for a symbol.

        Args:
            symbol: Stock symbol
            lookback_days: Days of historical data to analyze (default 30)

        Returns:
            ResearchInsights with confidence scores for each dimension

        Raises:
            ValueError: If symbol not found or insufficient data
        """
        as_of_date = date.today()
        cutoff_date = as_of_date - timedelta(days=lookback_days)

        # Collect data from all sources in parallel (conceptually)
        news_data = self._aggregate_news_intelligence(symbol, cutoff_date, as_of_date)
        fundamental_data = self._aggregate_fundamental_analysis(symbol)
        technical_data = self._aggregate_technical_analysis(symbol, as_of_date)
        macro_data = self._aggregate_macro_context(as_of_date)
        sector_data = self._aggregate_sector_strength(symbol, as_of_date)

        # Calculate overall confidence (weighted average)
        overall_confidence = self._calculate_overall_confidence(
            news_data["confidence"],
            fundamental_data["confidence"],
            technical_data["confidence"],
            1.0,  # macro always available
            sector_data["confidence"],
        )

        # Classify research quality
        research_quality: Literal["high", "medium", "low"]
        if overall_confidence >= 0.8:
            research_quality = "high"
        elif overall_confidence >= 0.5:
            research_quality = "medium"
        else:
            research_quality = "low"

        return ResearchInsights(
            symbol=symbol,
            as_of_date=as_of_date,
            # News intelligence
            news_sentiment_trend=news_data["sentiment_trend"],
            news_sentiment_score=news_data["sentiment_score"],
            news_sentiment_7d_avg=news_data["sentiment_7d_avg"],
            news_sentiment_30d_avg=news_data["sentiment_30d_avg"],
            material_events=news_data["material_events"],
            news_volume=news_data["news_volume"],
            news_confidence=news_data["confidence"],
            # Fundamental analysis
            company_health=fundamental_data["company_health"],
            fundamental_score=fundamental_data["fundamental_score"],
            valuation_tier=fundamental_data["valuation_tier"],
            growth_tier=fundamental_data["growth_tier"],
            profitability_tier=fundamental_data["profitability_tier"],
            debt_tier=fundamental_data["debt_tier"],
            analyst_consensus=fundamental_data["analyst_consensus"],
            fundamental_confidence=fundamental_data["confidence"],
            # Technical analysis
            trend_strength=technical_data["trend_strength"],
            trend_duration_days=technical_data["trend_duration_days"],
            momentum_rating=technical_data["momentum_rating"],
            volume_profile=technical_data["volume_profile"],
            rsi_zone=technical_data["rsi_zone"],
            price_vs_ma=technical_data["price_vs_ma"],
            technical_confidence=technical_data["confidence"],
            # Macro context
            market_regime=macro_data["market_regime"],
            fear_greed_score=macro_data["fear_greed_score"],
            fear_greed_classification=macro_data["fear_greed_classification"],
            sector_rotation_phase=macro_data["sector_rotation_phase"],
            # Sector strength
            sector=sector_data["sector"],
            sector_momentum=sector_data["sector_momentum"],
            sector_vs_spy_30d=sector_data["sector_vs_spy_30d"],
            sector_rotation_signal=sector_data["sector_rotation_signal"],
            # Overall assessment
            overall_confidence=overall_confidence,
            research_quality=research_quality,
            last_updated=datetime.now(),
        )

    def _fetch_news_data(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[dict[str, Any]]:
        """Fetch news articles from the cache.

        Args:
            symbol: Stock symbol
            start_date: Start of lookback period
            end_date: End of lookback period

        Returns:
            List of news article dicts with sentiment_score, published_at, headline
        """
        df = self.storage.get_news_data(symbol, str(start_date), str(end_date))
        if df.is_empty():
            return []
        return df.to_dicts()

    def _calculate_sentiment_metrics(
        self, news_rows: list[dict[str, Any]], end_date: date
    ) -> dict[str, Any]:
        """Calculate sentiment metrics from news data.

        Args:
            news_rows: List of news article dicts
            end_date: End of lookback period

        Returns:
            Dict with sentiment_score, sentiment_7d_avg, sentiment_30d_avg, sentiment_trend
        """
        all_scores = [
            row["sentiment_score"] for row in news_rows if row["sentiment_score"] is not None
        ]
        # Convert end_date to datetime for comparison with published_at (which is datetime)
        end_datetime = datetime.combine(end_date, datetime.min.time())
        recent_7d = [
            row["sentiment_score"]
            for row in news_rows
            if row["sentiment_score"] is not None
            and row["published_at"] is not None
            and (
                row["published_at"].replace(tzinfo=None)
                if hasattr(row["published_at"], "replace")
                else row["published_at"]
            )
            >= (end_datetime - timedelta(days=7))
        ]

        sentiment_score = all_scores[0] if all_scores else 0.0  # Most recent
        sentiment_7d_avg = sum(recent_7d) / len(recent_7d) if recent_7d else 0.0
        sentiment_30d_avg = sum(all_scores) / len(all_scores) if all_scores else 0.0

        # Determine sentiment trend
        if sentiment_7d_avg > sentiment_30d_avg + 0.1:
            sentiment_trend = "improving"
        elif sentiment_7d_avg < sentiment_30d_avg - 0.1:
            sentiment_trend = "deteriorating"
        else:
            sentiment_trend = "stable"

        return {
            "sentiment_score": sentiment_score,
            "sentiment_7d_avg": sentiment_7d_avg,
            "sentiment_30d_avg": sentiment_30d_avg,
            "sentiment_trend": sentiment_trend,
        }

    def _aggregate_news_intelligence(
        self, symbol: str, start_date: date, end_date: date
    ) -> dict[str, Any]:
        """Aggregate news sentiment and events.

        Args:
            symbol: Stock symbol
            start_date: Start of lookback period
            end_date: End of lookback period (today)

        Returns:
            Dict with news intelligence fields
        """
        news_rows = self._fetch_news_data(symbol, start_date, end_date)

        if not news_rows:
            # No news data available
            return {
                "sentiment_trend": "stable",
                "sentiment_score": 0.0,
                "sentiment_7d_avg": 0.0,
                "sentiment_30d_avg": 0.0,
                "material_events": [],
                "news_volume": 0,
                "confidence": 0.0,
            }

        # Calculate metrics using extracted helpers
        sentiment_data = self._calculate_sentiment_metrics(news_rows, end_date)
        material_events = _extract_material_events(news_rows)
        news_volume = len(news_rows)
        confidence = _calculate_news_confidence(news_volume)

        return {
            "sentiment_trend": sentiment_data["sentiment_trend"],
            "sentiment_score": sentiment_data["sentiment_score"],
            "sentiment_7d_avg": sentiment_data["sentiment_7d_avg"],
            "sentiment_30d_avg": sentiment_data["sentiment_30d_avg"],
            "material_events": material_events,
            "news_volume": news_volume,
            "confidence": confidence,
        }

    def _aggregate_fundamental_analysis(self, symbol: str) -> dict[str, Any]:
        """Aggregate fundamental metrics and company health.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with fundamental analysis fields
        """
        # Fetch fundamentals using existing multi-source failover
        fund_data: FundamentalData | None = fetch_fundamentals(symbol)

        if not fund_data:
            # No fundamental data available
            return {
                "company_health": "WEAK",
                "fundamental_score": 0,
                "valuation_tier": "fair",
                "growth_tier": "stable",
                "profitability_tier": "weak",
                "debt_tier": "moderate",
                "analyst_consensus": 3.0,
                "confidence": 0.0,
            }

        # Classify company health using existing logic
        company_health = classify_company_health(fund_data)

        # Calculate fundamental score using the same 4-pillar system as watchlist
        # This ensures consistency: research aggregator matches watchlist UI
        fundamental_score = int(calculate_fundamental_score(fund_data))

        # Classify valuation tier
        profit_margin = fund_data.profit_margin or 0.0
        if profit_margin > 0.20:
            valuation_tier = "undervalued"
        elif profit_margin < 0.05:
            valuation_tier = "overvalued"
        else:
            valuation_tier = "fair"

        # Classify growth tier
        revenue_growth = fund_data.revenue_growth or 0.0
        if revenue_growth > 0.30:
            growth_tier = "accelerating"
        elif revenue_growth < 0.0:
            growth_tier = "slowing"
        else:
            growth_tier = "stable"

        # Classify profitability tier
        if profit_margin > 0.20:
            profitability_tier = "excellent"
        elif profit_margin > 0.10:
            profitability_tier = "good"
        else:
            profitability_tier = "weak"

        # Classify debt tier
        debt_to_equity = fund_data.debt_to_equity or 0.5
        if debt_to_equity < 0.3:
            debt_tier = "low"
        elif debt_to_equity > 2.0:
            debt_tier = "high"
        else:
            debt_tier = "moderate"

        # Analyst consensus (1=strong buy, 5=sell)
        analyst_consensus = fund_data.recommendation_mean or 3.0

        # Confidence based on data completeness
        fields_present = sum(
            [
                fund_data.profit_margin is not None,
                fund_data.revenue_growth is not None,
                fund_data.debt_to_equity is not None,
                fund_data.recommendation_mean is not None,
            ]
        )
        confidence = fields_present / 4.0

        return {
            "company_health": company_health,
            "fundamental_score": fundamental_score,
            "valuation_tier": valuation_tier,
            "growth_tier": growth_tier,
            "profitability_tier": profitability_tier,
            "debt_tier": debt_tier,
            "analyst_consensus": analyst_consensus,
            "confidence": confidence,
        }

    def _calculate_trend_duration(self, symbol: str, trend_strength: str, sma_20: float) -> int:
        """Calculate trend duration in days above/below key moving average.

        Args:
            symbol: Stock symbol
            trend_strength: Current trend classification
            sma_20: 20-day simple moving average

        Returns:
            Number of days in current trend
        """
        df = self.storage.get_ohlcv_data(symbol, limit=60)
        if df.is_empty():
            return 0

        trend_rows = df.to_dicts()
        trend_duration_days = 0
        if trend_rows:
            for i, row in enumerate(trend_rows):
                if trend_strength in ["strong_up", "weak_up"]:
                    if row["close"] > sma_20:
                        trend_duration_days = i + 1
                    else:
                        break
                elif trend_strength in ["strong_down", "weak_down"]:
                    if row["close"] < sma_20:
                        trend_duration_days = i + 1
                    else:
                        break
                else:
                    break
        return trend_duration_days

    def _analyze_volume_profile(self, symbol: str) -> Literal["increasing", "stable", "decreasing"]:
        """Analyze volume profile by comparing recent to average volume.

        Args:
            symbol: Stock symbol

        Returns:
            Volume profile classification
        """
        df = self.storage.get_ohlcv_data(symbol, limit=20)
        if df.is_empty():
            return "stable"

        volume_rows = df.to_dicts()
        if volume_rows and len(volume_rows) >= 20:
            recent_5d_avg = sum(row["volume"] for row in volume_rows[:5]) / 5
            recent_20d_avg = sum(row["volume"] for row in volume_rows) / 20
            if recent_5d_avg > recent_20d_avg * 1.2:
                return "increasing"
            if recent_5d_avg < recent_20d_avg * 0.8:
                return "decreasing"
        return "stable"

    def _aggregate_technical_analysis(self, symbol: str, as_of_date: date) -> dict[str, Any]:
        """Aggregate technical indicators and trends.

        Args:
            symbol: Stock symbol
            as_of_date: Date to analyze

        Returns:
            Dict with technical analysis fields
        """
        # Calculate indicators using existing function
        indicators = calculate_indicators_for_symbol(
            symbol, indicators=["rsi", "macd", "sma_20", "sma_50", "sma_200", "ema_20", "atr"]
        )

        if not indicators:
            # No technical data available
            return {
                "trend_strength": "neutral",
                "trend_duration_days": 0,
                "momentum_rating": "steady",
                "volume_profile": "stable",
                "rsi_zone": "healthy",
                "price_vs_ma": {"20d": 1.0, "50d": 1.0, "200d": 1.0},
                "confidence": 0.0,
            }

        # Get current price
        current_price = self.storage.get_current_price(symbol)
        if current_price is None:
            current_price = 100.0

        # Extract indicators
        rsi_14 = indicators.get("rsi_14", 50.0)
        sma_20 = indicators.get("sma_20", current_price)
        sma_50 = indicators.get("sma_50", current_price)
        sma_200 = indicators.get("sma_200", current_price)

        # Classify trend strength using helper
        trend_strength = _classify_trend_strength(current_price, sma_20, sma_50, sma_200)

        # Calculate trend duration (days above/below key moving average)
        trend_duration_days = self._calculate_trend_duration(symbol, trend_strength, sma_20)

        # Classify momentum using helper
        macd_data = indicators.get("macd_12_26_9", {})
        momentum_rating = _analyze_momentum(macd_data)

        # Volume profile (requires recent volume data)
        volume_profile = self._analyze_volume_profile(symbol)

        # RSI zone classification using helper
        rsi_zone = _classify_rsi_zone(rsi_14)

        # Price vs moving averages
        price_vs_ma = {
            "20d": round(current_price / sma_20, 4) if sma_20 > 0 else 1.0,
            "50d": round(current_price / sma_50, 4) if sma_50 > 0 else 1.0,
            "200d": round(current_price / sma_200, 4) if sma_200 > 0 else 1.0,
        }

        # Confidence (1.0 if we have 252 days of data)
        bar_count_val = self.storage.get_bar_count(symbol)
        confidence = 1.0 if bar_count_val >= 252 else (bar_count_val / 252.0)

        return {
            "trend_strength": trend_strength,
            "trend_duration_days": trend_duration_days,
            "momentum_rating": momentum_rating,
            "volume_profile": volume_profile,
            "rsi_zone": rsi_zone,
            "price_vs_ma": price_vs_ma,
            "confidence": confidence,
        }

    def _aggregate_macro_context(self, as_of_date: date) -> dict[str, Any]:
        """Aggregate macro indicators (Fear & Greed, market regime).

        Args:
            as_of_date: Date to analyze

        Returns:
            Dict with macro context fields
        """
        # Query Fear & Greed from database
        fg_data = self.storage.get_fear_greed_latest()
        fear_greed_score = fg_data["score"]

        # Classify Fear & Greed
        if fear_greed_score <= 25:
            fear_greed_classification = "extreme_fear"
        elif fear_greed_score <= 45:
            fear_greed_classification = "fear"
        elif fear_greed_score <= 55:
            fear_greed_classification = "neutral"
        elif fear_greed_score <= 75:
            fear_greed_classification = "greed"
        else:
            fear_greed_classification = "extreme_greed"

        # Determine market regime (simplified logic)
        # Query SPY trend and VIX
        spy_indicators = calculate_indicators_for_symbol("SPY", indicators=["sma_200"])
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT close
                FROM day_bars
                WHERE symbol = 'SPY'
                ORDER BY date DESC
                LIMIT 1
                """
            )
            rows = result_wrapper.fetchall()
            spy_price_rows = rows_to_dicts(rows, conn)

            result_wrapper = conn.execute(
                """
                SELECT close as vix_close
                FROM day_bars
                WHERE symbol = '^VIX'
                ORDER BY date DESC
                LIMIT 1
                """
            )
            rows = result_wrapper.fetchall()
            vix_rows = rows_to_dicts(rows, conn)

        spy_price = float(spy_price_rows[0]["close"]) if spy_price_rows else 450.0
        spy_sma_200 = spy_indicators.get("sma_200", spy_price)
        vix_close = float(vix_rows[0]["vix_close"]) if vix_rows else 15.0

        # Market regime classification
        if vix_close > 30:
            market_regime = "volatile"
        elif fear_greed_score > 60 and spy_price > spy_sma_200:
            market_regime = "bull"
        elif fear_greed_score < 40 and spy_price < spy_sma_200:
            market_regime = "bear"
        else:
            market_regime = "range"

        # Sector rotation phase (simplified, based on VIX + Fear & Greed)
        if vix_close > 25:
            sector_rotation_phase = "recession"
        elif fear_greed_score > 70:
            sector_rotation_phase = "late_cycle"
        elif fear_greed_score > 55:
            sector_rotation_phase = "mid_cycle"
        else:
            sector_rotation_phase = "early_cycle"

        return {
            "market_regime": market_regime,
            "fear_greed_score": fear_greed_score,
            "fear_greed_classification": fear_greed_classification,
            "sector_rotation_phase": sector_rotation_phase,
        }

    def _aggregate_sector_strength(self, symbol: str, as_of_date: date) -> dict[str, Any]:
        """Aggregate sector relative strength vs SPY.

        Args:
            symbol: Stock symbol
            as_of_date: Date to analyze

        Returns:
            Dict with sector strength fields
        """
        # Query sector from watchlist metadata (stored as JSON) or fallback to Unknown
        # Note: watchlist_items has no 'sector' column - sector is stored in metadata JSON
        sector = "Unknown"
        try:
            with self.conn.connection() as conn:
                result_wrapper = conn.execute(
                    """
                    SELECT metadata
                    FROM watchlist_items
                    WHERE symbol = %s
                    LIMIT 1
                    """,
                    [symbol],
                )
                rows = result_wrapper.fetchall()
                meta_rows = rows_to_dicts(rows, conn)

            if meta_rows and meta_rows[0].get("metadata"):
                metadata = meta_rows[0]["metadata"]
                if isinstance(metadata, dict):
                    sector = metadata.get("sector", "Unknown")
        except Exception as e:
            logger.warning(f"Could not fetch sector for {symbol}: {e}")

        # If no sector mapping, return defaults
        if sector == "Unknown" or not sector:
            return {
                "sector": "Unknown",
                "sector_momentum": "in_line",
                "sector_vs_spy_30d": 0.0,
                "sector_rotation_signal": "hold",
                "confidence": 0.0,
            }

        # Calculate 30-day return for symbol and SPY
        symbol_return = self._calculate_30d_return(symbol)
        spy_return = self._calculate_30d_return("SPY")

        sector_vs_spy_30d = symbol_return - spy_return

        # Classify sector momentum
        if sector_vs_spy_30d > 5.0:
            sector_momentum = "leading"
        elif sector_vs_spy_30d < -5.0:
            sector_momentum = "lagging"
        else:
            sector_momentum = "in_line"

        # Sector rotation signal
        if sector_vs_spy_30d > 10.0:
            sector_rotation_signal = "hold"  # Already strong, hold position
        elif sector_vs_spy_30d > 0.0:
            sector_rotation_signal = "rotate_in"  # Strengthening, add exposure
        else:
            sector_rotation_signal = "rotate_out"  # Weakening, reduce exposure

        return {
            "sector": sector,
            "sector_momentum": sector_momentum,
            "sector_vs_spy_30d": sector_vs_spy_30d,
            "sector_rotation_signal": sector_rotation_signal,
            "confidence": 1.0,  # Always have sector data if symbol found
        }

    def _calculate_30d_return(self, symbol: str) -> float:
        """Calculate 30-day return for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            30-day return percentage
        """
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT close
                FROM day_bars
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 31
                """,
                [symbol],
            )
            rows_tuple = result_wrapper.fetchall()
            rows = rows_to_dicts(rows_tuple, conn)

        if not rows or len(rows) < 2:
            return 0.0

        current_price = float(rows[0]["close"])
        price_30d_ago = float(rows[-1]["close"])

        return ((current_price - price_30d_ago) / price_30d_ago) * 100.0

    def _calculate_overall_confidence(
        self,
        news_conf: float,
        fundamental_conf: float,
        technical_conf: float,
        macro_conf: float,
        sector_conf: float,
    ) -> float:
        """Calculate weighted average confidence across all dimensions.

        Args:
            news_conf: News intelligence confidence (0-1)
            fundamental_conf: Fundamental analysis confidence (0-1)
            technical_conf: Technical analysis confidence (0-1)
            macro_conf: Macro context confidence (0-1, always 1.0)
            sector_conf: Sector strength confidence (0-1)

        Returns:
            Overall confidence score (0-1)
        """
        # Weights (sum to 1.0)
        weights = {
            "news": 0.25,
            "fundamental": 0.30,
            "technical": 0.30,
            "macro": 0.10,
            "sector": 0.05,
        }

        weighted_sum = (
            news_conf * weights["news"]
            + fundamental_conf * weights["fundamental"]
            + technical_conf * weights["technical"]
            + macro_conf * weights["macro"]
            + sector_conf * weights["sector"]
        )

        return round(weighted_sum, 2)


# Singleton instance
_aggregator_instance: ResearchAggregationService | None = None


def get_research_aggregator() -> ResearchAggregationService:
    """Get singleton instance of research aggregation service."""
    global _aggregator_instance  # noqa: PLW0603
    if _aggregator_instance is None:
        _aggregator_instance = ResearchAggregationService()
    return _aggregator_instance

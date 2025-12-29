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
from app.storage.connection import get_connection_manager
from app.utils.db_helpers import rows_to_dicts
from app.watchlist.fundamentals import (
    FundamentalData,
    calculate_fundamental_score,
    classify_company_health,
    fetch_fundamentals,
)

from .models import ResearchInsights

logger = logging.getLogger(__name__)


class ResearchAggregationService:
    """Service for aggregating market research from multiple sources."""

    def __init__(self) -> None:
        """Initialize research aggregation service."""
        self.storage = PortfolioStorage()
        self.conn = get_connection_manager()

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
        # Query news_cache table for 30-day sentiment
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT
                    sentiment_score,
                    published_at,
                    headline
                FROM news_cache
                WHERE symbol = %s
                  AND published_at >= %s
                  AND published_at <= %s
                ORDER BY published_at DESC
                """,
                [symbol, str(start_date), str(end_date)],
            )
            rows = result_wrapper.fetchall()
            news_rows = _rows_to_dicts(rows, conn)

        if not news_rows or len(news_rows) == 0:
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

        # Calculate sentiment metrics
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

        # Extract material events from headlines (keyword-based classification)
        # Note: is_material_event column does not exist in news_cache schema
        material_events = []
        for row in news_rows:
            headline = row.get("headline", "")
            if not headline:
                continue
            headline_lower = headline.lower()
            # Simple event classification based on keywords
            if any(kw in headline_lower for kw in ["earnings", "beat", "miss", "eps", "revenue"]):
                material_events.append("earnings")
            elif any(kw in headline_lower for kw in ["product", "launch", "release", "announce"]):
                material_events.append("product_launch")
            elif any(kw in headline_lower for kw in ["acquisition", "merger", "acquire", "buyout"]):
                material_events.append("acquisition")
            elif any(kw in headline_lower for kw in ["fda", "approval", "regulatory", "sec"]):
                material_events.append("regulatory")

        # Deduplicate events
        material_events = list(set(material_events))

        # Confidence based on article count and source quality
        news_volume = len(news_rows)
        if news_volume >= 20:
            confidence = 1.0
        elif news_volume >= 10:
            confidence = 0.8
        elif news_volume >= 5:
            confidence = 0.6
        else:
            confidence = 0.4

        return {
            "sentiment_trend": sentiment_trend,
            "sentiment_score": sentiment_score,
            "sentiment_7d_avg": sentiment_7d_avg,
            "sentiment_30d_avg": sentiment_30d_avg,
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
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT close
                FROM day_bars
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 1
                """,
                [symbol],
            )
            rows = result_wrapper.fetchall()
            price_rows = _rows_to_dicts(rows, conn)
        current_price = float(price_rows[0]["close"]) if price_rows else 100.0

        # Extract indicators
        rsi_14 = indicators.get("rsi_14", 50.0)
        sma_20 = indicators.get("sma_20", current_price)
        sma_50 = indicators.get("sma_50", current_price)
        sma_200 = indicators.get("sma_200", current_price)

        # Classify trend strength
        if current_price > sma_20 and current_price > sma_50 and current_price > sma_200:
            if current_price / sma_200 > 1.10:
                trend_strength = "strong_up"
            else:
                trend_strength = "weak_up"
        elif current_price < sma_20 and current_price < sma_50 and current_price < sma_200:
            if current_price / sma_200 < 0.90:
                trend_strength = "strong_down"
            else:
                trend_strength = "weak_down"
        else:
            trend_strength = "neutral"

        # Calculate trend duration (days above/below key moving average)
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT date, close
                FROM day_bars
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 60
                """,
                [symbol],
            )
            rows = result_wrapper.fetchall()
            trend_rows = _rows_to_dicts(rows, conn)
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

        # Classify momentum using MACD
        macd_data = indicators.get("macd_12_26_9", {})
        macd_hist = macd_data.get("histogram", 0.0) if isinstance(macd_data, dict) else 0.0
        if macd_hist > 1.0:
            momentum_rating = "accelerating"
        elif macd_hist < -1.0:
            momentum_rating = "decelerating"
        else:
            momentum_rating = "steady"

        # Volume profile (requires recent volume data)
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT volume
                FROM day_bars
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 20
                """,
                [symbol],
            )
            rows = result_wrapper.fetchall()
            volume_rows = _rows_to_dicts(rows, conn)
        if volume_rows and len(volume_rows) >= 20:
            recent_5d_avg = sum(row["volume"] for row in volume_rows[:5]) / 5
            recent_20d_avg = sum(row["volume"] for row in volume_rows) / 20
            if recent_5d_avg > recent_20d_avg * 1.2:
                volume_profile = "increasing"
            elif recent_5d_avg < recent_20d_avg * 0.8:
                volume_profile = "decreasing"
            else:
                volume_profile = "stable"
        else:
            volume_profile = "stable"

        # RSI zone classification
        if rsi_14 < 30:
            rsi_zone = "oversold"
        elif rsi_14 > 70:
            rsi_zone = "overbought"
        else:
            rsi_zone = "healthy"

        # Price vs moving averages
        price_vs_ma = {
            "20d": round(current_price / sma_20, 4) if sma_20 > 0 else 1.0,
            "50d": round(current_price / sma_50, 4) if sma_50 > 0 else 1.0,
            "200d": round(current_price / sma_200, 4) if sma_200 > 0 else 1.0,
        }

        # Confidence (1.0 if we have 252 days of data)
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                "SELECT COUNT(*) as count FROM day_bars WHERE symbol = %s", [symbol]
            )
            rows = result_wrapper.fetchall()
            bar_count = _rows_to_dicts(rows, conn)
        bar_count_val = bar_count[0]["count"] if bar_count else 0
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
        with self.conn.connection() as conn:
            result_wrapper = conn.execute(
                """
                SELECT score, signal_count
                FROM fear_greed_daily
                ORDER BY as_of_date DESC
                LIMIT 1
                """
            )
            rows = result_wrapper.fetchall()
            fg_rows = _rows_to_dicts(rows, conn)

        if fg_rows and fg_rows[0]["score"] is not None:
            fear_greed_score = int(fg_rows[0]["score"])
        else:
            fear_greed_score = 50  # Neutral default

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
            spy_price_rows = _rows_to_dicts(rows, conn)

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
            vix_rows = _rows_to_dicts(rows, conn)

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
                meta_rows = _rows_to_dicts(rows, conn)

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
            rows = _rows_to_dicts(rows_tuple, conn)

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

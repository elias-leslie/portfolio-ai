"""Data quality service for watchlist symbols.

Calculates per-pillar data completeness and freshness for each symbol.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from ..logging_config import get_logger
from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Status values for data quality
StatusType = Literal["complete", "partial", "stale", "n/a"]

# Pillar weights for overall score calculation
PILLAR_WEIGHTS = {
    "technical": 25.0,
    "fundamental": 25.0,
    "catalyst": 15.0,
    "options": 10.0,
    "price": 25.0,
}


@dataclass
class PillarQuality:
    """Quality assessment for a single scoring pillar.

    Attributes:
        status: Overall status (complete/partial/stale/n/a)
        score: Quality score from 0-100
        details: Human-readable explanation (e.g., "1307 days, updated today")
    """

    status: StatusType
    score: float
    details: str

    def __post_init__(self) -> None:
        """Validate score is in valid range."""
        self.score = max(0.0, min(100.0, self.score))


@dataclass
class DataQuality:
    """Overall data quality assessment for a symbol.

    Attributes:
        overall_pct: Weighted average quality score (0-100)
        pillars: Per-pillar quality assessments
    """

    overall_pct: float
    pillars: dict[str, PillarQuality]

    def __post_init__(self) -> None:
        """Validate overall_pct is in valid range."""
        self.overall_pct = max(0.0, min(100.0, self.overall_pct))


def _check_technical_quality(
    storage: PortfolioStorage, symbol: str, now: datetime
) -> PillarQuality:
    """Check technical indicators data quality.

    Technical pillar is complete if:
    - technical_indicators row exists for this symbol
    - date field is today's date
    - At least 5 core indicators are non-null (RSI, MACD, SMA_20, EMA_20, volume)

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        now: Current datetime for freshness checks

    Returns:
        PillarQuality for technical pillar
    """
    try:
        df = storage.query(
            """
            SELECT
                date,
                rsi_14,
                macd,
                sma_20,
                ema_20,
                sma_50,
                sma_200,
                calculated_at
            FROM technical_indicators
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT 1
            """,
            [symbol],
        )

        if df.is_empty():
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No technical indicators data",
            )

        row = df.to_dicts()[0]
        indicator_date = row.get("date")
        calculated_at = row.get("calculated_at")

        # Count non-null indicators
        indicator_fields = ["rsi_14", "macd", "sma_20", "ema_20", "sma_50", "sma_200"]
        non_null_count = sum(1 for field in indicator_fields if row.get(field) is not None)
        total_fields = len(indicator_fields)

        # Check freshness (should be today or yesterday for daily indicators)
        today = now.date()
        yesterday = today - timedelta(days=1)

        is_fresh = False
        days_old = 0
        if isinstance(indicator_date, datetime):
            indicator_date = indicator_date.date()

        if indicator_date:
            days_old = (today - indicator_date).days
            is_fresh = indicator_date in (today, yesterday)

        # Calculate score: data presence (70%) + freshness (30%)
        presence_score = (non_null_count / total_fields) * 70.0
        freshness_score = 30.0 if is_fresh else max(0.0, 30.0 - (days_old * 3.0))
        score = presence_score + freshness_score

        # Determine status
        if non_null_count == total_fields and is_fresh:
            status: StatusType = "complete"
        elif non_null_count >= 4 and days_old <= 3:
            status = "partial"
        elif days_old > 3:
            status = "stale"
        else:
            status = "partial"

        details = f"{non_null_count}/{total_fields} indicators"
        if indicator_date:
            details += f", {days_old}d old"
        if calculated_at and isinstance(calculated_at, datetime):
            hours_ago = int((now - calculated_at).total_seconds() / 3600)
            details += f", calc {hours_ago}h ago"

        return PillarQuality(status=status, score=score, details=details)

    except Exception as e:
        logger.error("technical_quality_check_failed", symbol=symbol, error=str(e))
        return PillarQuality(status="n/a", score=0.0, details=f"Error: {e!s}")


def _check_fundamental_quality(
    storage: PortfolioStorage, symbol: str, now: datetime
) -> PillarQuality:
    """Check fundamental data quality.

    Fundamental pillar is complete if:
    - reference_cache has valuation data
    - profit_margin and debt_to_equity are not null
    - Data is from the last quarter (< 120 days old)

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        now: Current datetime for freshness checks

    Returns:
        PillarQuality for fundamental pillar
    """
    try:
        df = storage.query(
            """
            SELECT
                as_of_date,
                payload
            FROM reference_cache
            WHERE symbol = ?
            AND source = 'yfinance_valuation'
            ORDER BY as_of_date DESC
            LIMIT 1
            """,
            [symbol],
        )

        if df.is_empty():
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No fundamental data",
            )

        row = df.to_dicts()[0]
        as_of_date = row.get("as_of_date")
        payload = row.get("payload") or {}

        # Check for key valuation metrics
        profit_margin = payload.get("profit_margin")
        debt_to_equity = payload.get("debt_to_equity")
        revenue_growth = payload.get("revenue_growth")
        pe_ratio = payload.get("pe_ratio")

        metrics = [profit_margin, debt_to_equity, revenue_growth, pe_ratio]
        non_null_count = sum(1 for m in metrics if m is not None)
        total_metrics = len(metrics)

        # Check freshness (quarterly data, so < 120 days is good)
        today = now.date()
        days_old = 0
        is_fresh = False

        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.date()

        if as_of_date:
            days_old = (today - as_of_date).days
            is_fresh = days_old <= 120  # Quarterly data

        # Calculate score: data presence (60%) + freshness (40%)
        presence_score = (non_null_count / total_metrics) * 60.0
        if is_fresh:
            freshness_score = 40.0
        elif days_old <= 240:  # Two quarters
            freshness_score = 20.0
        else:
            freshness_score = 0.0

        score = presence_score + freshness_score

        # Determine status
        if non_null_count >= 3 and is_fresh:
            status: StatusType = "complete"
        elif non_null_count >= 2 and days_old <= 240:
            status = "partial"
        elif days_old > 240:
            status = "stale"
        else:
            status = "partial"

        details = f"{non_null_count}/{total_metrics} metrics"
        if as_of_date:
            details += f", {days_old}d old"

        return PillarQuality(status=status, score=score, details=details)

    except Exception as e:
        logger.error("fundamental_quality_check_failed", symbol=symbol, error=str(e))
        return PillarQuality(status="n/a", score=0.0, details=f"Error: {e!s}")


def _check_catalyst_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    """Check catalyst data quality.

    Catalyst pillar is complete if:
    - earnings_surprises OR insider_transactions exist in last 90 days
    - At least one recent catalyst event

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        now: Current datetime for freshness checks

    Returns:
        PillarQuality for catalyst pillar
    """
    try:
        cutoff_date_dt = now - timedelta(days=90)

        # Check earnings surprises
        earnings_df = storage.query(
            """
            SELECT COUNT(*) as count, MAX(earnings_date) as latest_date
            FROM earnings_surprises
            WHERE symbol = ?
            AND earnings_date >= ?
            """,
            [symbol, cutoff_date_dt],
        )

        # Check insider transactions
        insider_df = storage.query(
            """
            SELECT COUNT(*) as count, MAX(transaction_date) as latest_date
            FROM insider_transactions
            WHERE symbol = ?
            AND transaction_date >= ?
            """,
            [symbol, cutoff_date_dt],
        )

        earnings_count = 0
        insider_count = 0
        latest_earnings = None
        latest_insider = None

        if not earnings_df.is_empty():
            earnings_row = earnings_df.to_dicts()[0]
            earnings_count = earnings_row.get("count", 0)
            latest_earnings = earnings_row.get("latest_date")

        if not insider_df.is_empty():
            insider_row = insider_df.to_dicts()[0]
            insider_count = insider_row.get("count", 0)
            latest_insider = insider_row.get("latest_date")

        total_count = earnings_count + insider_count

        if total_count == 0:
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No catalyst events in 90d",
            )

        # Find most recent event
        most_recent = None
        if latest_earnings and latest_insider:
            most_recent = max(latest_earnings, latest_insider)
        elif latest_earnings:
            most_recent = latest_earnings
        elif latest_insider:
            most_recent = latest_insider

        # Calculate days since most recent event
        days_since = 0
        if most_recent:
            if isinstance(most_recent, datetime):
                most_recent = most_recent.date()
            days_since = (now.date() - most_recent).days

        # Calculate score based on recency and count
        # More recent = higher score, more events = higher score
        recency_score = max(0.0, 50.0 - (days_since * 0.5))
        count_score = min(50.0, total_count * 10.0)
        score = recency_score + count_score

        # Determine status
        if total_count >= 2 and days_since <= 30:
            status: StatusType = "complete"
        elif total_count >= 1 and days_since <= 60:
            status = "partial"
        else:
            status = "partial"

        details = f"{total_count} events in 90d"
        if most_recent:
            details += f", latest {days_since}d ago"
        if earnings_count > 0:
            details += f" ({earnings_count} earnings)"
        if insider_count > 0:
            details += f" ({insider_count} insider)"

        return PillarQuality(status=status, score=score, details=details)

    except Exception as e:
        logger.error("catalyst_quality_check_failed", symbol=symbol, error=str(e))
        return PillarQuality(status="n/a", score=0.0, details=f"Error: {e!s}")


def _check_options_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    """Check options flow data quality.

    Options pillar is complete if:
    - options_market_metrics table has recent data (last 7 days)
    - This is market-wide data, not symbol-specific

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol (unused, options data is market-wide)
        now: Current datetime for freshness checks

    Returns:
        PillarQuality for options pillar
    """
    try:
        cutoff_date_dt = now - timedelta(days=7)

        df = storage.query(
            """
            SELECT COUNT(*) as count, MAX(as_of_date) as latest_date
            FROM options_market_metrics
            WHERE as_of_date >= ?
            """,
            [cutoff_date_dt],
        )

        if df.is_empty():
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No options market data",
            )

        row = df.to_dicts()[0]
        count = row.get("count", 0)
        latest_date = row.get("latest_date")

        if count == 0:
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No options data in 7d",
            )

        # Calculate days since latest data
        days_old = 0
        if latest_date:
            if isinstance(latest_date, datetime):
                latest_date = latest_date.date()
            days_old = (now.date() - latest_date).days

        # Calculate score: freshness is key for options data
        if days_old <= 1:
            score = 100.0
            status: StatusType = "complete"
        elif days_old <= 3:
            score = 70.0
            status = "partial"
        elif days_old <= 7:
            score = 40.0
            status = "partial"
        else:
            score = 0.0
            status = "stale"

        details = f"{count} days in 7d, latest {days_old}d ago"

        return PillarQuality(status=status, score=score, details=details)

    except Exception as e:
        logger.error("options_quality_check_failed", symbol=symbol, error=str(e))
        return PillarQuality(status="n/a", score=0.0, details=f"Error: {e!s}")


def _check_price_quality(storage: PortfolioStorage, symbol: str, now: datetime) -> PillarQuality:
    """Check price data quality.

    Price pillar is complete if:
    - day_bars has data within 1 day (accounts for weekends/holidays)
    - Close price is present

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        now: Current datetime for freshness checks

    Returns:
        PillarQuality for price pillar
    """
    try:
        df = storage.query(
            """
            SELECT
                date,
                close,
                volume
            FROM day_bars
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT 1
            """,
            [symbol],
        )

        if df.is_empty():
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No price data",
            )

        row = df.to_dicts()[0]
        price_date = row.get("date")
        close = row.get("close")
        volume = row.get("volume")

        if close is None:
            return PillarQuality(
                status="n/a",
                score=0.0,
                details="No close price",
            )

        # Check freshness (within 1 day for daily bars)
        today = now.date()
        days_old = 0

        if isinstance(price_date, datetime):
            price_date = price_date.date()

        if price_date:
            days_old = (today - price_date).days

        # Calculate score: freshness is critical for price data
        if days_old <= 1:
            score = 100.0
            status: StatusType = "complete"
        elif days_old <= 3:
            score = 60.0
            status = "partial"
        elif days_old <= 7:
            score = 30.0
            status = "stale"
        else:
            score = 0.0
            status = "stale"

        details = f"close ${close:.2f}"
        if price_date:
            details += f", {days_old}d old"
        if volume:
            volume_str = f"{volume:,.0f}" if volume >= 1000 else f"{volume:.0f}"
            details += f", vol {volume_str}"

        return PillarQuality(status=status, score=score, details=details)

    except Exception as e:
        logger.error("price_quality_check_failed", symbol=symbol, error=str(e))
        return PillarQuality(status="n/a", score=0.0, details=f"Error: {e!s}")


def calculate_data_quality(storage: PortfolioStorage, symbols: list[str]) -> dict[str, DataQuality]:
    """Calculate data quality for multiple symbols.

    Checks each pillar (technical, fundamental, catalyst, options, price) and
    returns an overall weighted quality score.

    Args:
        storage: PortfolioStorage instance
        symbols: List of stock symbols to check

    Returns:
        Dict mapping symbol to DataQuality assessment

    Example:
        >>> storage = get_storage()
        >>> quality = calculate_data_quality(storage, ["AAPL", "MSFT"])
        >>> print(quality["AAPL"].overall_pct)
        87.5
        >>> print(quality["AAPL"].pillars["technical"].status)
        "complete"
    """
    if not symbols:
        return {}

    now = datetime.now(UTC)
    results: dict[str, DataQuality] = {}

    logger.info("calculating_data_quality", symbol_count=len(symbols))

    for symbol in symbols:
        try:
            # Check each pillar
            technical = _check_technical_quality(storage, symbol, now)
            fundamental = _check_fundamental_quality(storage, symbol, now)
            catalyst = _check_catalyst_quality(storage, symbol, now)
            options = _check_options_quality(storage, symbol, now)
            price = _check_price_quality(storage, symbol, now)

            # Calculate weighted overall score
            weighted_sum = (
                technical.score * PILLAR_WEIGHTS["technical"]
                + fundamental.score * PILLAR_WEIGHTS["fundamental"]
                + catalyst.score * PILLAR_WEIGHTS["catalyst"]
                + options.score * PILLAR_WEIGHTS["options"]
                + price.score * PILLAR_WEIGHTS["price"]
            )
            total_weight = sum(PILLAR_WEIGHTS.values())
            overall_pct = weighted_sum / total_weight

            results[symbol] = DataQuality(
                overall_pct=overall_pct,
                pillars={
                    "technical": technical,
                    "fundamental": fundamental,
                    "catalyst": catalyst,
                    "options": options,
                    "price": price,
                },
            )

            logger.debug(
                "symbol_quality_calculated",
                symbol=symbol,
                overall_pct=overall_pct,
                technical_status=technical.status,
                fundamental_status=fundamental.status,
                catalyst_status=catalyst.status,
                options_status=options.status,
                price_status=price.status,
            )

        except Exception as e:
            logger.error("symbol_quality_calculation_failed", symbol=symbol, error=str(e))
            # Return minimal quality on error
            results[symbol] = DataQuality(
                overall_pct=0.0,
                pillars={
                    "technical": PillarQuality("n/a", 0.0, "Error"),
                    "fundamental": PillarQuality("n/a", 0.0, "Error"),
                    "catalyst": PillarQuality("n/a", 0.0, "Error"),
                    "options": PillarQuality("n/a", 0.0, "Error"),
                    "price": PillarQuality("n/a", 0.0, "Error"),
                },
            )

    logger.info(
        "data_quality_calculation_complete",
        symbol_count=len(symbols),
        avg_quality=sum(r.overall_pct for r in results.values()) / len(results) if results else 0.0,
    )

    return results

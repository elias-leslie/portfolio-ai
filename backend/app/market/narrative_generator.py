"""Market narrative generation system.

Generates plain-language, actionable narratives from market data.
Zero jargon, focused on helping amateur investors understand and act.
Uses dynamic weekly % changes for concrete, meaningful insights.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WeeklyChanges:
    """Weekly % changes for key market indicators."""

    vix: float | None = None
    sp500: float | None = None
    tnx: float | None = None
    dxy: float | None = None


@dataclass
class SectorWeeklyChange:
    """Weekly % change for a sector with friendly name."""

    name: str  # Friendly name like "Technology", "Healthcare"
    change_pct: float | None


def _format_change(pct: float | None, name: str) -> str:
    """Format a % change into readable text.

    Args:
        pct: Percentage change (can be negative)
        name: Human-readable name of the indicator

    Returns:
        Formatted string like "VIX climbed 8%" or "S&P 500 fell 2%"
    """
    if pct is None:
        return ""

    if abs(pct) < 0.5:
        return f"{name} was flat"
    if pct > 0:
        verb = "climbed" if pct > 3 else "rose"
        return f"{name} {verb} {abs(pct):.1f}%"
    verb = "dropped" if pct < -3 else "fell"
    return f"{name} {verb} {abs(pct):.1f}%"


# Actionable recommendations based on conditions
RECOMMENDATIONS: dict[str, str] = {
    "stay_invested": "Good time to stay invested.",
    "selective": "Be selective with new positions.",
    "quality_focus": "Focus on quality names.",
    "defensive_stance": "Consider defensive positions.",
    "wait_and_see": "Wait for better opportunities.",
    "opportunity": "This could be a buying opportunity for patient investors.",
}


def _determine_sentiment(health_score: int, fg_score: int) -> str:
    """Determine overall market sentiment from scores.

    Args:
        health_score: Market health score (0-100)
        fg_score: Fear & Greed score (0-100)

    Returns:
        Sentiment description: "very bullish", "bullish", "balanced", etc.
    """
    avg_score = (health_score + fg_score) / 2

    if avg_score >= 75:
        return "very bullish"
    if avg_score >= 60:
        return "bullish"
    if avg_score >= 40:
        return "balanced"
    if avg_score >= 25:
        return "cautious"
    return "fearful"


def _get_recommendation(sentiment: str, vix_change: float | None) -> str:
    """Get actionable recommendation based on market conditions.

    Args:
        sentiment: Overall sentiment description
        vix_change: Weekly VIX change (positive = volatility increased)

    Returns:
        Recommendation key for RECOMMENDATIONS dict
    """
    if sentiment in ("very bullish", "bullish"):
        return "stay_invested"
    if sentiment == "balanced":
        return "selective"
    if sentiment == "cautious":
        return "defensive_stance"
    # Contrarian: extreme fear + high volatility spike = opportunity
    if sentiment == "fearful" and vix_change is not None and vix_change > 20:
        return "opportunity"
    if sentiment == "fearful":
        return "wait_and_see"
    return "quality_focus"


def _build_indicator_sentence(weekly: WeeklyChanges) -> str:
    """Build a sentence describing key indicator moves this week.

    Args:
        weekly: Weekly % changes for indicators

    Returns:
        Sentence like "VIX climbed 8% this week while S&P 500 fell 2%."
    """
    parts: list[str] = []

    # VIX is most important for volatility context
    if weekly.vix is not None and abs(weekly.vix) >= 3:
        parts.append(_format_change(weekly.vix, "VIX"))

    # S&P 500 for overall market direction
    if weekly.sp500 is not None and abs(weekly.sp500) >= 1:
        parts.append(_format_change(weekly.sp500, "S&P 500"))

    # Treasury yields if notable move
    if weekly.tnx is not None and abs(weekly.tnx) >= 3:
        parts.append(_format_change(weekly.tnx, "Treasury yields"))

    # Dollar if notable move
    if weekly.dxy is not None and abs(weekly.dxy) >= 2:
        parts.append(_format_change(weekly.dxy, "the dollar"))

    if not parts:
        return "Markets are quiet so far this week."

    if len(parts) == 1:
        return f"{parts[0]} this week vs last."

    # Join with "while" - lowercase the verb only, not the proper noun
    second_part = parts[1]
    # Only lowercase if first word is a common word (not VIX, S&P, Treasury)
    if second_part.startswith(("the ", "a ")):
        second_part = second_part.lower()
    return f"{parts[0]} this week while {second_part}."


def _build_sector_sentence(sectors: list[SectorWeeklyChange]) -> str:
    """Build a sentence about sector performance.

    Args:
        sectors: List of sector weekly changes (should be sorted by change_pct desc)

    Returns:
        Sentence about leading/lagging sectors with friendly names
    """
    if not sectors:
        return ""

    # Filter to sectors with valid data
    valid_sectors = [s for s in sectors if s.change_pct is not None]
    if not valid_sectors:
        return ""

    # Get top 2 performers and bottom 2
    sorted_sectors = sorted(valid_sectors, key=lambda s: s.change_pct or 0, reverse=True)

    top_sectors = sorted_sectors[:2]
    bottom_sectors = sorted_sectors[-2:] if len(sorted_sectors) > 2 else []

    # Check if broadly positive or negative
    avg_change = sum(s.change_pct or 0 for s in valid_sectors) / len(valid_sectors)

    if avg_change > 2:
        # Broad rally - mention leaders
        leaders = ", ".join(s.name for s in top_sectors)
        return f"Sectors rallied broadly, led by {leaders}."
    if avg_change < -2:
        # Broad selloff
        laggers = ", ".join(s.name for s in bottom_sectors)
        return f"Sectors sold off broadly, with {laggers} hit hardest."
    # Mixed - show rotation
    if top_sectors and bottom_sectors:
        top_names = " and ".join(s.name for s in top_sectors)
        bottom_names = " and ".join(s.name for s in bottom_sectors)
        return f"{top_names} outperformed while {bottom_names} lagged."

    return ""


def generate_market_narrative(
    health_score: int,
    fg_score: int,
    vix_price: float | None,
    sp500_price: float | None,
    tnx_yield: float | None,
    dxy_price: float | None,
    leading_sectors: list[str],
    weekly_changes: WeeklyChanges | None = None,
    sector_changes: list[SectorWeeklyChange] | None = None,
) -> str:
    """Generate actionable market narrative from current conditions.

    Uses dynamic weekly % changes for concrete, meaningful insights.

    Args:
        health_score: Market health score (0-100)
        fg_score: Fear & Greed Index score (0-100)
        vix_price: Current VIX price
        sp500_price: Current S&P 500 price
        tnx_yield: Current 10Y Treasury yield
        dxy_price: Current US Dollar Index price
        leading_sectors: List of top performing sector names (plain language) - legacy
        weekly_changes: Weekly % changes for key indicators (VIX, S&P, etc.)
        sector_changes: Weekly % changes for sectors with friendly names

    Returns:
        3-4 sentence actionable narrative with dynamic weekly data

    Example:
        >>> narrative = generate_market_narrative(
        ...     health_score=68,
        ...     fg_score=72,
        ...     vix_price=15.2,
        ...     sp500_price=4825.0,
        ...     tnx_yield=4.1,
        ...     dxy_price=104.5,
        ...     leading_sectors=["Technology", "Financials"],
        ...     weekly_changes=WeeklyChanges(vix=-5.2, sp500=2.1, tnx=1.5, dxy=-0.8),
        ...     sector_changes=[
        ...         SectorWeeklyChange("Technology", 3.5),
        ...         SectorWeeklyChange("Healthcare", -1.2),
        ...     ]
        ... )
        >>> print(narrative)
        Markets are bullish today. VIX fell 5.2% this week while S&P 500 rose 2.1%.
        Technology outperformed while Healthcare lagged. Good time to stay invested.
    """
    sentiment = _determine_sentiment(health_score, fg_score)
    vix_change = weekly_changes.vix if weekly_changes else None
    recommendation = _get_recommendation(sentiment, vix_change)

    sentences: list[str] = []

    # Sentence 1: Overall sentiment (simpler, no redundant scores)
    sentences.append(f"Markets are {sentiment} today.")

    # Sentence 2: Dynamic indicator changes (if available)
    if weekly_changes:
        indicator_sentence = _build_indicator_sentence(weekly_changes)
        if indicator_sentence:
            sentences.append(indicator_sentence)

    # Sentence 3: Sector rotation with friendly names
    if sector_changes:
        sector_sentence = _build_sector_sentence(sector_changes)
        if sector_sentence:
            sentences.append(sector_sentence)

    # Sentence 4: Actionable recommendation
    sentences.append(RECOMMENDATIONS[recommendation])

    return " ".join(sentences)


def generate_simple_narrative(health_score: int, fg_score: int) -> str:
    """Generate simple narrative from scores only (fallback when data incomplete).

    Args:
        health_score: Market health score (0-100)
        fg_score: Fear & Greed Index score (0-100)

    Returns:
        Simple 1-2 sentence narrative
    """
    sentiment = _determine_sentiment(health_score, fg_score)
    recommendation = _get_recommendation(sentiment, None)

    return f"Markets are {sentiment} today. {RECOMMENDATIONS[recommendation]}"

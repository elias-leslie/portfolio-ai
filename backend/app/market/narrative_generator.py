"""Market narrative generation system.

Generates plain-language, actionable narratives from market data.
Zero jargon, focused on helping amateur investors understand and act.
"""

from __future__ import annotations

# Narrative templates for different market conditions
MARKET_NARRATIVE_TEMPLATES: dict[str, str] = {
    # Overall sentiment templates
    "very_bullish": "Markets are very bullish today (Health: {health_score}/100, Fear & Greed: {fg_score}/100).",
    "bullish": "Markets are healthy today (Health: {health_score}/100, Fear & Greed: {fg_score}/100).",
    "neutral": "Markets are balanced today (Health: {health_score}/100, Fear & Greed: {fg_score}/100).",
    "bearish": "Markets are cautious today (Health: {health_score}/100, Fear & Greed: {fg_score}/100).",
    "very_bearish": "Markets are fearful today (Health: {health_score}/100, Fear & Greed: {fg_score}/100).",
    # Volatility context
    "low_volatility": "Low volatility shows investor confidence.",
    "normal_volatility": "Normal volatility levels suggest steady markets.",
    "high_volatility": "High volatility signals market uncertainty.",
    "extreme_volatility": "Extreme volatility indicates panic or major uncertainty.",
    # S&P 500 levels
    "strong_sp500": "Strong S&P levels favor staying invested.",
    "moderate_sp500": "Moderate S&P levels suggest selective opportunities.",
    "weak_sp500": "Weak S&P levels warrant caution.",
    # Sector rotation patterns
    "tech_leading": "Technology and growth sectors are leading.",
    "defensive_leading": "Defensive sectors like Utilities and Healthcare are leading.",
    "cyclical_leading": "Cyclical sectors like Energy and Financials are leading.",
    "broad_strength": "Strength is broad across sectors.",
    "narrow_leadership": "Leadership is narrow - only a few sectors performing well.",
    "rotation_to_safety": "Money is rotating to safe-haven sectors.",
    # Bond yield context
    "healthy_yields": "Moderate bond yields support stock valuations.",
    "low_yields": "Low yields may signal recession concerns.",
    "high_yields": "High yields create headwinds for stocks.",
    # Dollar strength
    "weak_dollar": "A weak dollar supports international stocks and exports.",
    "moderate_dollar": "Dollar at moderate levels.",
    "strong_dollar": "Dollar strength may pressure international stocks.",
    # Actionable recommendations
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
        Sentiment key: very_bullish, bullish, neutral, bearish, very_bearish
    """
    # Average the two scores for overall sentiment
    avg_score = (health_score + fg_score) / 2

    if avg_score >= 75:
        return "very_bullish"
    if avg_score >= 60:
        return "bullish"
    if avg_score >= 40:
        return "neutral"
    if avg_score >= 25:
        return "bearish"
    return "very_bearish"


def _get_volatility_context(vix_price: float | None) -> str:
    """Get volatility context narrative.

    Args:
        vix_price: Current VIX price

    Returns:
        Volatility context key
    """
    if vix_price is None:
        return "normal_volatility"

    if vix_price < 15:
        return "low_volatility"
    if vix_price < 25:
        return "normal_volatility"
    if vix_price < 35:
        return "high_volatility"
    return "extreme_volatility"


def _get_sp500_context(sp500_price: float | None) -> str:
    """Get S&P 500 level context.

    Args:
        sp500_price: Current S&P 500 price

    Returns:
        S&P context key
    """
    if sp500_price is None:
        return "moderate_sp500"

    # These thresholds will need updating over time as markets evolve
    if sp500_price > 4800:
        return "strong_sp500"
    if sp500_price > 4000:
        return "moderate_sp500"
    return "weak_sp500"


def _get_yield_context(tnx_yield: float | None) -> str:
    """Get bond yield context.

    Args:
        tnx_yield: Current 10Y Treasury yield

    Returns:
        Yield context key
    """
    if tnx_yield is None:
        return "healthy_yields"

    if 3.5 <= tnx_yield <= 4.5:
        return "healthy_yields"
    if tnx_yield < 3.0:
        return "low_yields"
    return "high_yields"


def _get_dollar_context(dxy_price: float | None) -> str:
    """Get dollar strength context.

    Args:
        dxy_price: Current DXY price

    Returns:
        Dollar context key
    """
    if dxy_price is None:
        return "moderate_dollar"

    if dxy_price < 100:
        return "weak_dollar"
    if dxy_price < 105:
        return "moderate_dollar"
    return "strong_dollar"


def _get_sector_rotation_context(leading_sectors: list[str]) -> str:
    """Get sector rotation narrative.

    Args:
        leading_sectors: List of leading sector names (plain language)

    Returns:
        Sector rotation context key
    """
    if not leading_sectors:
        return "broad_strength"

    # Check for specific rotation patterns
    tech_leading = any(s in ["Technology", "Communication Services"] for s in leading_sectors)
    defensive_leading = any(
        s in ["Utilities", "Healthcare", "Consumer Staples"] for s in leading_sectors
    )
    cyclical_leading = any(s in ["Energy", "Financials", "Materials"] for s in leading_sectors)

    if len(leading_sectors) >= 6:
        return "broad_strength"
    if defensive_leading and not tech_leading:
        return "defensive_leading"
    if cyclical_leading:
        return "cyclical_leading"
    if tech_leading:
        return "tech_leading"

    return "narrow_leadership"


def _get_recommendation(sentiment: str, volatility_context: str) -> str:
    """Get actionable recommendation based on market conditions.

    Args:
        sentiment: Overall sentiment (very_bullish, bullish, etc.)
        volatility_context: Volatility context (low, normal, high, extreme)

    Returns:
        Recommendation key
    """
    # Combine bullish cases (reduces from 7 to 6 return statements)
    if sentiment in ("very_bullish", "bullish"):
        return "stay_invested"
    if sentiment == "neutral":
        return "selective"
    if sentiment == "bearish":
        return "defensive_stance"
    if sentiment == "very_bearish" and volatility_context == "extreme_volatility":
        return "opportunity"  # Contrarian: extreme fear = opportunity
    if sentiment == "very_bearish":
        return "wait_and_see"

    return "quality_focus"


def generate_market_narrative(
    health_score: int,
    fg_score: int,
    vix_price: float | None,
    sp500_price: float | None,
    tnx_yield: float | None,
    dxy_price: float | None,
    leading_sectors: list[str],
) -> str:
    """Generate actionable market narrative from current conditions.

    Args:
        health_score: Market health score (0-100)
        fg_score: Fear & Greed Index score (0-100)
        vix_price: Current VIX price
        sp500_price: Current S&P 500 price
        tnx_yield: Current 10Y Treasury yield
        dxy_price: Current US Dollar Index price
        leading_sectors: List of top performing sector names (plain language)

    Returns:
        3-4 sentence actionable narrative with recommendations

    Example:
        >>> narrative = generate_market_narrative(
        ...     health_score=68,
        ...     fg_score=72,
        ...     vix_price=15.2,
        ...     sp500_price=4825.0,
        ...     tnx_yield=4.1,
        ...     dxy_price=104.5,
        ...     leading_sectors=["Technology", "Financials", "Energy"]
        ... )
        >>> print(narrative)
        Markets are healthy today (Health: 68/100, Fear & Greed: 72/100).
        Low volatility shows investor confidence. Technology and growth
        sectors are leading. Good time to stay invested.
    """
    # Determine contexts
    sentiment = _determine_sentiment(health_score, fg_score)
    volatility_context = _get_volatility_context(vix_price)
    sp500_context = _get_sp500_context(sp500_price)
    yield_context = _get_yield_context(tnx_yield)
    dollar_context = _get_dollar_context(dxy_price)
    sector_context = _get_sector_rotation_context(leading_sectors)
    recommendation = _get_recommendation(sentiment, volatility_context)

    # Build narrative
    sentences: list[str] = []

    # Sentence 1: Overall sentiment with scores
    sentiment_template = MARKET_NARRATIVE_TEMPLATES[sentiment]
    sentences.append(sentiment_template.format(health_score=health_score, fg_score=fg_score))

    # Sentence 2: Key market context (volatility OR S&P level)
    # Choose most relevant based on sentiment
    if volatility_context in ["high_volatility", "extreme_volatility", "low_volatility"]:
        sentences.append(MARKET_NARRATIVE_TEMPLATES[volatility_context])
    else:
        sentences.append(MARKET_NARRATIVE_TEMPLATES[sp500_context])

    # Sentence 3: Sector rotation OR yield/dollar context
    if sector_context != "broad_strength":
        sentences.append(MARKET_NARRATIVE_TEMPLATES[sector_context])
    # If sectors are broad, mention yields or dollar if notable
    elif yield_context in ["low_yields", "high_yields"]:
        sentences.append(MARKET_NARRATIVE_TEMPLATES[yield_context])
    elif dollar_context in ["weak_dollar", "strong_dollar"]:
        sentences.append(MARKET_NARRATIVE_TEMPLATES[dollar_context])
    else:
        sentences.append(MARKET_NARRATIVE_TEMPLATES["broad_strength"])

    # Sentence 4: Actionable recommendation
    sentences.append(MARKET_NARRATIVE_TEMPLATES[recommendation])

    # Join into paragraph
    return " ".join(sentences)


def generate_simple_narrative(health_score: int, fg_score: int) -> str:
    """Generate simple narrative from scores only (fallback when data incomplete).

    Args:
        health_score: Market health score (0-100)
        fg_score: Fear & Greed Index score (0-100)

    Returns:
        Simple 1-2 sentence narrative

    Example:
        >>> narrative = generate_simple_narrative(68, 72)
        >>> print(narrative)
        Markets are healthy today (Health: 68/100, Fear & Greed: 72/100).
        Good time to stay invested.
    """
    sentiment = _determine_sentiment(health_score, fg_score)
    recommendation = _get_recommendation(sentiment, "normal_volatility")

    sentiment_template = MARKET_NARRATIVE_TEMPLATES[sentiment]
    sentiment_text = sentiment_template.format(health_score=health_score, fg_score=fg_score)

    recommendation_text = MARKET_NARRATIVE_TEMPLATES[recommendation]

    return f"{sentiment_text} {recommendation_text}"

"""Narrative generation and signal classification for watchlist intelligence."""

from __future__ import annotations

from typing import Any

from .models import SignalClassification, SignalStrength, SignalType

# Narrative templates: Translate technical indicators to plain language (zero jargon)
NARRATIVE_TEMPLATES: dict[str, str] = {
    # Trend templates
    "uptrend": "Stock is in an uptrend (rising steadily)",
    "downtrend": "Stock is in a downtrend (falling steadily)",
    "sideways": "Stock is moving sideways (range-bound)",
    # Entry templates
    "pullback": "Just pulled back to a good entry point",
    "breakout": "Breaking out to new highs",
    "support": "Bouncing off support level",
    # Momentum templates
    "momentum_positive": "Momentum is positive (buyers are in control)",
    "momentum_negative": "Momentum is negative (sellers are in control)",
    "momentum_neutral": "Momentum is neutral (waiting for direction)",
    # Volume templates
    "volume_high": "Excellent volume - strong conviction",
    "volume_low": "Low volume - weak participation",
    "volume_average": "Normal volume - steady activity",
    # Condition templates
    "overbought": "Already extended - just hit new high",
    "oversold": "Oversold - potential bounce opportunity",
    "healthy": "Healthy pullback - normal profit-taking",
    # Company health templates
    "excellent_company": "Top-tier company with strong fundamentals",
    "good_company": "Solid company with decent fundamentals",
    "weak_company": "Struggling company with weak fundamentals",
    # News templates
    "positive_news": "Recent positive news driving interest",
    "negative_news": "Recent negative news causing concern",
    "neutral_news": "News flow is neutral",
}


def generate_headline(classification: SignalClassification) -> str:
    """Generate a plain-language headline for the signal classification.

    Args:
        classification: Signal classification with type, strength, and reasons

    Returns:
        Headline string in format: "{SIGNAL_TYPE} - {primary_reason}"
    """
    signal_str = classification.signal_type.value  # BUY, HOLD, or AVOID

    # Add strength descriptor for BUY signals
    if classification.signal_type == SignalType.BUY:
        if classification.strength.value >= 8:
            signal_str = "STRONG BUY"
        elif classification.strength.value >= 6:
            signal_str = "BUY"

    # Extract primary reason (first reason is usually most important)
    if classification.reasons:
        # Take first reason and simplify it
        primary_reason = classification.reasons[0]
        # Remove technical details in parentheses if present
        if "(" in primary_reason:
            primary_reason = primary_reason.split("(")[0].strip()
    # Fallback reason based on signal type
    elif classification.signal_type == SignalType.BUY:
        primary_reason = "Good setup"
    elif classification.signal_type == SignalType.AVOID:
        primary_reason = "Risk factors present"
    else:
        primary_reason = "Mixed signals"

    return f"{signal_str} - {primary_reason}"


def generate_technical_bullets(inputs: dict[str, Any]) -> list[str]:
    """Generate plain-language technical setup bullets (zero jargon).

    Args:
        inputs: Dictionary containing technical indicator values

    Returns:
        List of 3-5 plain-language bullet points
    """
    bullets: list[str] = []

    # Extract inputs
    price = inputs.get("price", 0.0)
    ema_20 = inputs.get("ema_20", 0.0)
    rsi_14 = inputs.get("rsi_14", 50.0)
    macd = inputs.get("macd", 0.0)
    volume = inputs.get("volume", 0.0)
    volume_avg_20 = inputs.get("volume_avg_20", 0.0)

    # Translate price vs EMA (trend)
    if price > 0 and ema_20 > 0:
        if price > ema_20:
            pct_above = ((price - ema_20) / ema_20) * 100
            if pct_above >= 5:
                bullets.append("Strong uptrend - making higher highs")
            else:
                bullets.append("In uptrend - rising steadily")
        else:
            pct_below = ((ema_20 - price) / ema_20) * 100
            if pct_below >= 5:
                bullets.append("In downtrend - falling steadily")
            else:
                bullets.append("Below recent average - weak trend")

    # Translate RSI (momentum condition)
    if rsi_14 > 70:
        bullets.append("Already extended - just hit new high")
    elif rsi_14 < 30:
        bullets.append("Oversold - potential bounce opportunity")
    elif 40 <= rsi_14 <= 60:
        bullets.append("Healthy momentum - normal trading")
    elif rsi_14 < 40:
        bullets.append("Some weakness showing - sellers active")

    # Translate MACD (momentum direction)
    if macd > 0:
        bullets.append("Buyers active - momentum positive")
    elif macd < 0:
        bullets.append("Sellers active - momentum negative")

    # Translate volume
    if volume_avg_20 > 0 and volume > 0:
        volume_ratio = volume / volume_avg_20
        if volume_ratio >= 1.5:
            bullets.append("Excellent volume - strong conviction")
        elif volume_ratio >= 0.7:
            bullets.append("Normal volume - steady activity")
        else:
            bullets.append("Low volume - weak participation")

    # Ensure we have at least 3 bullets
    if len(bullets) < 3:
        bullets.append("Limited technical data available")

    return bullets[:5]  # Cap at 5 bullets


# Index ETF list for style classification
INDEX_ETFS = {"SPY", "VOO", "VTI", "QQQ", "IWM", "DIA", "AGG", "BND"}


def generate_company_health_bullets(fundamentals: dict[str, Any]) -> list[str]:
    """Generate plain-language company health bullets (zero jargon).

    Args:
        fundamentals: Dictionary containing fundamental data:
            - revenue_growth: Revenue growth rate (0.10 = 10%)
            - profit_margin: Profit margin (0.15 = 15%)
            - debt_to_equity: Debt-to-equity ratio
            - cash: Cash on hand (in dollars)
            - analyst_buy_pct: Percentage of analysts with buy rating (0.75 = 75%)

    Returns:
        List of 3-5 plain-language bullet points with ✓/✗/⚠ symbols

    Example:
        >>> fundamentals = {
        ...     "revenue_growth": 1.22,
        ...     "profit_margin": 0.53,
        ...     "debt_to_equity": 0.15,
        ...     "cash": 26_000_000_000,
        ...     "analyst_buy_pct": 0.94,
        ... }
        >>> bullets = generate_company_health_bullets(fundamentals)
        >>> # Returns: ["✓ Growing fast - Revenue up 122% this year", ...]
    """
    bullets: list[str] = []

    # Extract fundamentals (all optional)
    revenue_growth = fundamentals.get("revenue_growth")
    profit_margin = fundamentals.get("profit_margin")
    debt_to_equity = fundamentals.get("debt_to_equity")
    cash = fundamentals.get("cash")
    analyst_buy_pct = fundamentals.get("analyst_buy_pct")

    # Revenue growth bullet
    if revenue_growth is not None:
        revenue_pct = revenue_growth * 100
        if revenue_growth >= 0.20:  # 20%+ growth
            bullets.append(f"✓ Growing fast - Revenue up {revenue_pct:.0f}% this year")
        elif revenue_growth >= 0.05:  # 5-20% growth
            bullets.append(f"✓ Steady growth - Revenue up {revenue_pct:.0f}% this year")
        elif revenue_growth >= 0:  # 0-5% growth
            bullets.append(f"⚠ Slow growth - Revenue up {revenue_pct:.0f}% this year")
        else:  # Negative growth
            bullets.append(f"✗ Shrinking - Revenue down {abs(revenue_pct):.0f}% this year")

    # Profit margin bullet
    if profit_margin is not None:
        margin_pct = profit_margin * 100
        if profit_margin >= 0.20:  # 20%+ margin
            bullets.append(f"✓ Very profitable - Profit margins {margin_pct:.0f}%")
        elif profit_margin >= 0.05:  # 5-20% margin
            bullets.append(f"✓ Profitable - Profit margins {margin_pct:.0f}%")
        elif profit_margin >= 0:  # 0-5% margin
            bullets.append(f"⚠ Low margins - Only {margin_pct:.0f}% profit")
        else:  # Negative margin
            bullets.append(f"✗ Unprofitable - Losing {abs(margin_pct):.0f}% on sales")

    # Balance sheet bullet (debt + cash)
    if debt_to_equity is not None or cash is not None:
        if debt_to_equity is not None and debt_to_equity < 0.5:
            # Low debt
            if cash is not None and cash >= 1_000_000_000:  # $1B+ cash
                cash_b = cash / 1_000_000_000
                bullets.append(f"✓ Strong balance sheet - ${cash_b:.0f}B cash, low debt")
            else:
                bullets.append("✓ Strong balance sheet - Low debt")
        elif debt_to_equity is not None and debt_to_equity < 1.5:
            # Moderate debt
            bullets.append("⚠ Moderate debt levels")
        elif debt_to_equity is not None and debt_to_equity >= 1.5:
            # High debt
            bullets.append(f"✗ High debt - Debt-to-equity {debt_to_equity:.1f}x")
        elif cash is not None and cash >= 5_000_000_000:
            # Only cash data available - $5B+ cash
            cash_b = cash / 1_000_000_000
            bullets.append(f"✓ Strong cash position - ${cash_b:.0f}B on hand")

    # Analyst ratings bullet
    if analyst_buy_pct is not None:
        buy_pct = analyst_buy_pct * 100
        if analyst_buy_pct >= 0.70:  # 70%+ buy
            bullets.append(f"✓ Analysts love it - {buy_pct:.0f}% buy ratings")
        elif analyst_buy_pct >= 0.50:  # 50-70% buy
            bullets.append(f"⚠ Mixed analyst views - {buy_pct:.0f}% buy ratings")
        else:  # <50% buy
            bullets.append(f"✗ Analysts cautious - Only {buy_pct:.0f}% buy ratings")

    # Ensure we have at least 1 bullet
    if len(bullets) == 0:
        bullets.append("⚠ Limited fundamental data available")

    return bullets[:5]  # Cap at 5 bullets


def generate_action_plan(
    signal_type: str,
    entry_price: float | None,
    stop_loss: float | None,
    profit_target: float | None,
) -> str:
    """Generate plain-language action plan for the trade.

    Args:
        signal_type: Signal type (BUY, HOLD, or AVOID)
        entry_price: Entry price for the trade
        stop_loss: Stop loss price
        profit_target: Profit target price

    Returns:
        Plain-language action plan text with entry, stop, target

    Example:
        >>> plan = generate_action_plan("BUY", 202.0, 195.0, 216.0)
        >>> # Returns multi-line text with entry/stop/target details
    """
    if signal_type == "AVOID":
        return (
            "⚠ RECOMMENDATION: Avoid this trade\n"
            "• Too many risk factors present\n"
            "• Better opportunities elsewhere\n"
            "• Stay on the sidelines for now"
        )

    if entry_price is None or stop_loss is None or profit_target is None:
        return "⚠ Unable to calculate trade plan - missing price data"

    # Calculate gain percentage
    gain_pct = ((profit_target - entry_price) / entry_price) * 100
    loss_pct = ((entry_price - stop_loss) / entry_price) * 100

    if signal_type == "BUY":
        return (
            f"💰 ACTION PLAN:\n"
            f"• BUY around ${entry_price:.2f} - quality setup\n"
            f"• EXIT if drops below ${stop_loss:.2f} (protect capital -{loss_pct:.1f}%)\n"
            f"• TAKE PROFIT at ${profit_target:.2f} (+{gain_pct:.1f}% gain)"
        )

    # HOLD signal
    return (
        f"👀 WATCH AND WAIT:\n"
        f"• Consider entry around ${entry_price:.2f} if setup improves\n"
        f"• Would exit below ${stop_loss:.2f} (risk -{loss_pct:.1f}%)\n"
        f"• Potential target ${profit_target:.2f} (+{gain_pct:.1f}% gain)\n"
        f"• Wait for stronger confirmation before buying"
    )


def generate_position_sizing_text(
    shares: int,
    entry_price: float,
    stop_loss: float,
    profit_target: float,
) -> str:
    """Generate plain-language position sizing narrative.

    Args:
        shares: Number of shares to buy
        entry_price: Entry price per share
        stop_loss: Stop loss price per share
        profit_target: Profit target price per share

    Returns:
        Plain-language text explaining investment, gain, and loss

    Example:
        >>> text = generate_position_sizing_text(71, 202.0, 195.0, 216.0)
        >>> # Returns text with investment amount, potential gain, max loss
    """
    if shares == 0:
        return (
            "⚠ HOW MUCH TO BUY: Too expensive for typical risk budget\n"
            "• Stock price requires larger capital allocation\n"
            "• Consider increasing risk budget or skip this trade\n"
            "• Wait for better entry point or lower-priced opportunities"
        )

    # Calculate values
    investment = shares * entry_price
    potential_gain = shares * (profit_target - entry_price)
    gain_pct = ((profit_target - entry_price) / entry_price) * 100
    max_loss = shares * (entry_price - stop_loss)
    loss_pct = ((entry_price - stop_loss) / entry_price) * 100

    return (
        f"📊 HOW MUCH TO BUY:\n"
        f"• Buy {shares:,} shares = ${investment:,.0f} invested\n"
        f"• Potential gain: +${potential_gain:,.0f} (+{gain_pct:.1f}%)\n"
        f"• Maximum loss: -${max_loss:,.0f} (-{loss_pct:.1f}%)"
    )


def generate_special_notes(
    signal_type: str,
    signal_strength: int,
    earnings_days_away: int | None,
    company_health: str,
) -> str:
    """Generate special notes and warnings (earnings, WHY THIS WORKS).

    Args:
        signal_type: Signal type (BUY, HOLD, or AVOID)
        signal_strength: Signal strength (0-10)
        earnings_days_away: Days until next earnings (None if unknown)
        company_health: Company health rating (EXCELLENT, GOOD, WEAK)

    Returns:
        Plain-language special notes text

    Example:
        >>> notes = generate_special_notes("BUY", 9, 3, "EXCELLENT")
        >>> # Returns text with earnings warning + WHY THIS WORKS
    """
    sections: list[str] = []

    # Earnings warnings (only if earnings soon)
    if earnings_days_away is not None:
        if earnings_days_away <= 5:
            # Imminent earnings (0-5 days) - red alert
            sections.append(
                f"🔴 EARNINGS IN {earnings_days_away} DAYS - High volatility expected\n"
                f"• Stock could move sharply on results\n"
                f"• Consider waiting until after earnings\n"
                f"• If entering, size smaller than usual"
            )
        elif earnings_days_away <= 14:
            # Earnings soon (6-14 days) - caution
            sections.append(
                f"⚠ Next Earnings: {earnings_days_away} days away\n"
                f"• Could see increased volatility ahead of report\n"
                f"• Watch for position sizing"
            )
        elif earnings_days_away <= 30:
            # Earnings approaching (15-30 days) - heads up
            sections.append(f"💡 Next Earnings: {earnings_days_away} days away")

    # WHY THIS WORKS explanation
    if signal_type == "BUY":
        why_text = "💡 WHY THIS WORKS:\n"
        if signal_strength >= 8:
            why_text += "• Strong technical setup + solid fundamentals align\n"
            if company_health == "EXCELLENT":
                why_text += "• Top-tier company with excellent growth metrics\n"
            why_text += "• Multiple confirming indicators pointing to upside\n"
            why_text += "• Good risk/reward at current levels"
        else:
            why_text += "• Decent technical setup with quality company\n"
            why_text += "• Fundamentals support the technical picture\n"
            why_text += "• Reasonable entry point for long-term holders"
        sections.append(why_text.rstrip())

    elif signal_type == "HOLD":
        sections.append(
            "💡 WHY HOLD:\n"
            "• Mixed technical signals - not ideal entry yet\n"
            "• Quality company but waiting for better setup\n"
            "• Watch for improvement before committing capital"
        )

    elif signal_type == "AVOID":
        sections.append(
            "💡 WHY AVOID:\n"
            "• Too many risk factors outweigh potential reward\n"
            "• Better opportunities available elsewhere\n"
            "• Protect capital and wait for clearer setup"
        )

    # Join sections with double newline
    return "\n\n".join(sections) if sections else ""


def classify_trading_style(
    symbol: str,
    signal_strength: int,
    signal_type: str,
    rsi_14: float,
    earnings_days_away: int | None,
) -> dict[str, Any]:
    """Classify recommended trading style using simplified heuristics.

    Classification hierarchy (checked in order):
    1. Index: Symbol in hardcoded ETF list
    2. Event: Earnings within 7 days
    3. Swing: RSI in reversal zones [30-40] or [60-70]
    4. Trend: Strong BUY signal (strength >= 8)
    5. Value: Default fallback

    Args:
        symbol: Stock ticker symbol
        signal_strength: Signal strength (0-10)
        signal_type: Signal type (BUY, HOLD, AVOID)
        rsi_14: 14-day RSI indicator
        earnings_days_away: Days until next earnings (None if unknown)

    Returns:
        Dictionary with:
        - style: Trading style (Index/Trend/Value/Swing/Event)
        - confidence: Confidence level (0-10)
        - holding_period: Recommended holding timeframe
        - risk_level: Risk profile (Low/Medium-Low/Medium/High)
    """
    # Index: Hardcoded ETF list (highest priority)
    if symbol.upper() in INDEX_ETFS:
        return {
            "style": "Index",
            "confidence": 10,
            "holding_period": "Hold indefinitely",
            "risk_level": "Low",
        }

    # Event: Earnings within 7 days (catalyst-driven)
    if earnings_days_away is not None and earnings_days_away < 7:
        return {
            "style": "Event",
            "confidence": 8,
            "holding_period": "Days to weeks",
            "risk_level": "High",
        }

    # Swing: RSI in reversal zones (oversold 30-40 or overbought 60-70)
    if (30 <= rsi_14 <= 40) or (60 <= rsi_14 <= 70):
        return {
            "style": "Swing",
            "confidence": 7,
            "holding_period": "1-3 weeks",
            "risk_level": "Medium",
        }

    # Trend: Strong BUY signal (strength >= 8)
    if signal_strength >= 8 and signal_type == "BUY":
        return {
            "style": "Trend",
            "confidence": 9,
            "holding_period": "2-3 months",
            "risk_level": "Medium",
        }

    # Value: Default fallback (patient hold)
    return {
        "style": "Value",
        "confidence": 6,
        "holding_period": "6-12 months",
        "risk_level": "Medium-Low",
    }


def classify_signal(inputs: dict[str, Any]) -> SignalClassification:
    """Classify watchlist signal as BUY, HOLD, or AVOID based on multiple indicators.

    Args:
        inputs: Dictionary containing:
            - price: Current stock price
            - ema_20: 20-day exponential moving average
            - sma_5: 5-day simple moving average
            - sma_5_prev: Previous 5-day SMA (for trend detection)
            - rsi_14: 14-day RSI indicator
            - macd: MACD indicator value
            - volume: Current volume
            - volume_avg_20: 20-day average volume
            - company_health: Company health rating (EXCELLENT, GOOD, WEAK)
            - news_sentiment: News sentiment score (-1.0 to +1.0)
            - earnings_days_away: Days until next earnings (optional)

    Returns:
        SignalClassification with type, strength, and reasons
    """
    reasons: list[str] = []
    confirmations = 0
    avoid_flags = 0  # Count of negative indicators

    # Extract inputs (handle None values with or operator)
    price = inputs.get("price", 0.0) or 0.0
    ema_20 = inputs.get("ema_20", 0.0) or 0.0
    sma_5 = inputs.get("sma_5", 0.0) or 0.0
    sma_5_prev = inputs.get("sma_5_prev", 0.0) or 0.0
    rsi_14 = inputs.get("rsi_14", 50.0) or 50.0
    macd = inputs.get("macd", 0.0) or 0.0
    volume = inputs.get("volume", 0.0) or 0.0
    volume_avg_20 = inputs.get("volume_avg_20", 0.0) or 0.0
    company_health = inputs.get("company_health", "") or ""
    news_sentiment = inputs.get("news_sentiment", 0.0) or 0.0
    earnings_days_away = inputs.get("earnings_days_away")

    # Check for AVOID signals (negative indicators)
    # AVOID Check 1: Price < 20-day EMA AND 5-day SMA declining
    if price < ema_20 and sma_5_prev > 0 and sma_5 < sma_5_prev:
        avoid_flags += 1
        reasons.append(f"Price ${price:.2f} below 20-day EMA ${ema_20:.2f} (downtrend)")

    # AVOID Check 2: News sentiment < -0.3 (significantly negative)
    if news_sentiment < -0.3:
        avoid_flags += 1
        reasons.append(f"News sentiment {news_sentiment:.2f} (significantly negative)")

    # AVOID Check 3: Earnings within 5 days (high volatility risk)
    if earnings_days_away is not None and earnings_days_away <= 5:
        avoid_flags += 1
        reasons.append(f"Earnings in {earnings_days_away} days (high volatility risk)")

    # AVOID Check 4: Company health = WEAK
    if company_health == "WEAK":
        avoid_flags += 1
        reasons.append(f"Company health: {company_health}")

    # AVOID: 2 or more negative flags (lowered from 3 for better detection)
    if avoid_flags >= 2:
        # More avoid flags = lower strength (inverted)
        # 2 flags → 4, 3 flags → 3, 4 flags → 2, 5 flags → 1, 6+ flags → 0
        strength_value = max(0, 6 - avoid_flags)
        return SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=strength_value),
            reasons=reasons,
        )

    # Check for BUY signals (positive indicators)
    # Check 1: Price > 20-day EMA (uptrend)
    if price > ema_20:
        confirmations += 1
        reasons.append(f"Price ${price:.2f} > 20-day EMA ${ema_20:.2f} (uptrend)")

    # Check 2: RSI between 30-70 (not extreme)
    if 30 <= rsi_14 <= 70:
        confirmations += 1
        reasons.append(f"RSI at {rsi_14:.0f} (healthy, not extreme)")

    # Check 3: MACD > 0 (positive momentum)
    if macd > 0:
        confirmations += 1
        reasons.append(f"MACD {macd:.2f} positive (momentum)")

    # Check 4: Volume >= 70% of 20-day average
    if volume_avg_20 > 0 and volume >= 0.7 * volume_avg_20:
        confirmations += 1
        volume_pct = (volume / volume_avg_20) * 100
        reasons.append(f"Volume {volume_pct:.0f}% of average (strong)")

    # Check 5: Company health = EXCELLENT or GOOD
    if company_health in ("EXCELLENT", "GOOD"):
        confirmations += 1
        reasons.append(f"Company health: {company_health}")

    # Check 6: News sentiment >= 0.2 (positive)
    if news_sentiment >= 0.2:
        confirmations += 1
        reasons.append(f"News sentiment {news_sentiment:.2f} (positive)")

    # Check 7: Not overbought (RSI <= 70)
    if rsi_14 <= 70:
        confirmations += 1

    # Check 8: Strong uptrend confirmation (price significantly above EMA)
    if ema_20 > 0 and (price - ema_20) / ema_20 >= 0.02:  # At least 2% above EMA
        confirmations += 1

    # Calculate signal strength (0-10 scale)
    # 8+ confirmations → 9/10, 5-7 → 6-8/10, 0-4 → 0-5/10
    if confirmations >= 8:
        strength_value = 9
    elif confirmations >= 7:
        strength_value = 8
    elif confirmations >= 6:
        strength_value = 7
    elif confirmations >= 5:
        strength_value = 6
    else:
        strength_value = min(confirmations, 5)

    # Determine signal type based on confirmations and specific criteria
    if confirmations >= 6:
        signal_type = SignalType.BUY
    else:
        signal_type = SignalType.HOLD

    return SignalClassification(
        signal_type=signal_type,
        strength=SignalStrength(value=strength_value),
        reasons=reasons,
    )

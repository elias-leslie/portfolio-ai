"""Narrative text generation for watchlist intelligence.

This module generates plain-language narratives from technical and fundamental data.
All generated text is designed to be zero-jargon and accessible to retail traders.
"""

from __future__ import annotations

from typing import Any

from .models import SignalClassification, SignalType

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


def _gen_revenue_bullet(revenue_growth: float) -> str:
    """Generate revenue growth bullet."""
    revenue_pct = revenue_growth * 100
    if revenue_growth >= 0.20:
        return f"✓ Growing fast - Revenue up {revenue_pct:.0f}% this year"
    if revenue_growth >= 0.05:
        return f"✓ Steady growth - Revenue up {revenue_pct:.0f}% this year"
    if revenue_growth >= 0:
        return f"⚠ Slow growth - Revenue up {revenue_pct:.0f}% this year"
    return f"✗ Shrinking - Revenue down {abs(revenue_pct):.0f}% this year"


def _gen_profit_bullet(profit_margin: float) -> str:
    """Generate profit margin bullet."""
    margin_pct = profit_margin * 100
    if profit_margin >= 0.20:
        return f"✓ Very profitable - Profit margins {margin_pct:.0f}%"
    if profit_margin >= 0.05:
        return f"✓ Profitable - Profit margins {margin_pct:.0f}%"
    if profit_margin >= 0:
        return f"⚠ Low margins - Only {margin_pct:.0f}% profit"
    return f"✗ Unprofitable - Losing {abs(margin_pct):.0f}% on sales"


def _gen_balance_sheet_bullet(debt_to_equity: float | None, cash: float | None) -> str | None:
    """Generate balance sheet health bullet."""
    # Debt analysis takes priority
    if debt_to_equity is not None:
        if debt_to_equity < 0.5 and cash is not None and cash >= 1_000_000_000:
            cash_b = cash / 1_000_000_000
            return f"✓ Strong balance sheet - ${cash_b:.0f}B cash, low debt"
        if debt_to_equity < 0.5:
            return "✓ Strong balance sheet - Low debt"
        if debt_to_equity < 1.5:
            return "⚠ Moderate debt levels"
        return f"✗ High debt - Debt-to-equity {debt_to_equity:.1f}x"

    # Cash-only analysis (no debt data)
    if cash is not None and cash >= 5_000_000_000:
        cash_b = cash / 1_000_000_000
        return f"✓ Strong cash position - ${cash_b:.0f}B on hand"

    return None


def _gen_analyst_bullet(analyst_buy_pct: float) -> str:
    """Generate analyst ratings bullet."""
    buy_pct = analyst_buy_pct * 100
    if analyst_buy_pct >= 0.70:
        return f"✓ Analysts love it - {buy_pct:.0f}% buy ratings"
    if analyst_buy_pct >= 0.50:
        return f"⚠ Mixed analyst views - {buy_pct:.0f}% buy ratings"
    return f"✗ Analysts cautious - Only {buy_pct:.0f}% buy ratings"


def generate_company_health_bullets(fundamentals: dict[str, Any]) -> list[str]:
    """Generate plain-language company health bullets (see helper functions for logic)."""
    bullets: list[str] = []

    # Extract fundamentals
    revenue_growth = fundamentals.get("revenue_growth")
    profit_margin = fundamentals.get("profit_margin")
    debt_to_equity = fundamentals.get("debt_to_equity")
    cash = fundamentals.get("cash")
    analyst_buy_pct = fundamentals.get("analyst_buy_pct")

    # Generate bullets using helpers
    if revenue_growth is not None:
        bullets.append(_gen_revenue_bullet(revenue_growth))

    if profit_margin is not None:
        bullets.append(_gen_profit_bullet(profit_margin))

    balance_bullet = _gen_balance_sheet_bullet(debt_to_equity, cash)
    if balance_bullet:
        bullets.append(balance_bullet)

    if analyst_buy_pct is not None:
        bullets.append(_gen_analyst_bullet(analyst_buy_pct))

    # Fallback if no data
    if not bullets:
        bullets.append("⚠ Limited fundamental data available")

    return bullets[:5]


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

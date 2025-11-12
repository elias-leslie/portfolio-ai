"""Narrative intelligence and trade level calculations for watchlist refresh.

This module handles:
- Signal classification (BUY/SELL/HOLD)
- Trading style classification
- Trade level calculations (entry, stop loss, profit target, position size)
- Narrative text generation (headlines, action plans, company health bullets)

Extracted from refresh_processor.py to improve modularity.
"""

from __future__ import annotations

from typing import Any, TypedDict, cast

from ..logging_config import get_logger
from ..portfolio.models import PriceData
from ..storage import PortfolioStorage
from .calculator import (
    calculate_entry_price,
    calculate_position_size,
    calculate_profit_target,
    calculate_stop_loss,
)
from .fundamentals import FundamentalData
from .models import SignalType, TechnicalSnapshot
from .narrative import (
    classify_signal,
    classify_trading_style,
    generate_action_plan,
    generate_company_health_bullets,
    generate_headline,
    generate_position_sizing_text,
    generate_special_notes,
)

logger = get_logger(__name__)


class TradingStyleDict(TypedDict):
    """Trading style classification result."""

    style: str
    confidence: int
    holding_period: str
    risk_level: str


class NarrativeResultDict(TypedDict):
    """Result from generate_narrative_and_trade_levels function."""

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


def build_signal_inputs(
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


def calculate_trade_levels(
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


def generate_narrative_texts(
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


def classify_signal_and_style(
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


def build_narrative_result(
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


def create_default_narrative_result(symbol: str) -> NarrativeResultDict:
    """Create default narrative result when generation fails."""
    return build_narrative_result(
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


def generate_narrative_and_trade_levels(
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
        signal_inputs = build_signal_inputs(
            price_data,
            technical_snapshot,
            current_volume,
            avg_volume_20d,
            sma_5_prev,
            company_health_str,
            news_sentiment_value,
            earnings_days_away_val,
        )
        signal_type, signal_strength, headline, style_result = classify_signal_and_style(
            symbol, signal_inputs, technical_snapshot.rsi_14, earnings_days_away_val
        )
        entry_price, stop_loss, profit_target, position_size = calculate_trade_levels(
            storage, symbol, price_data.price, signal_type, risk_budget
        )
        action_plan, position_sizing, company_health_bullets, special_notes = (
            generate_narrative_texts(
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
        return build_narrative_result(
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
        return create_default_narrative_result(symbol)

"""Market intelligence helpers for enriching and formatting market data.

This module provides functions for enriching market indicators with plain-language
labels and grouping sectors by performance.
"""

from __future__ import annotations

from app.market import plain_language
from app.market.sentiment import MarketHealthScore
from app.models.market_intelligence import EnrichedIndicator, SectorInfo
from app.portfolio.models import PriceData


def get_signal_emoji(signal: str) -> str:
    """Get emoji representation for a signal.

    Args:
        signal: Signal type (Bullish, Bearish, Neutral)

    Returns:
        Emoji string
    """
    if signal == "Bullish":
        return "🟢"
    if signal == "Bearish":
        return "🔴"
    return "🟡"


def enrich_vix_indicator(
    vix_data: PriceData,
    health_score_data: MarketHealthScore,
) -> EnrichedIndicator:
    """Enrich VIX indicator with plain-language labels.

    Args:
        vix_data: VIX price data
        health_score_data: Market health score with components

    Returns:
        Enriched VIX indicator
    """
    vix_label = plain_language.get_indicator_label("vix")
    vix_component = next((c for c in health_score_data.components if "VIX" in c.name), None)

    return EnrichedIndicator(
        value=vix_data.price,
        change_pct=None,
        label=vix_label["label"],
        short_label=vix_label["short"],
        tooltip=vix_label["tooltip"],
        signal=vix_component.signal if vix_component else "Neutral",
        emoji=get_signal_emoji(vix_component.signal if vix_component else "Neutral"),
        last_updated=vix_data.cached_at.isoformat(),
    )


def enrich_sp500_indicator(
    sp500_data: PriceData,
    health_score_data: MarketHealthScore,
) -> EnrichedIndicator:
    """Enrich S&P 500 indicator with plain-language labels.

    Args:
        sp500_data: S&P 500 price data
        health_score_data: Market health score with components

    Returns:
        Enriched S&P 500 indicator
    """
    sp500_label = plain_language.get_indicator_label("sp500")
    sp500_component = next((c for c in health_score_data.components if "S&P" in c.name), None)

    return EnrichedIndicator(
        value=sp500_data.price,
        change_pct=None,
        label=sp500_label["label"],
        short_label=sp500_label["short"],
        tooltip=sp500_label["tooltip"],
        signal=sp500_component.signal if sp500_component else "Neutral",
        emoji=get_signal_emoji(sp500_component.signal if sp500_component else "Neutral"),
        last_updated=sp500_data.cached_at.isoformat(),
    )


def enrich_tnx_indicator(
    tnx_data: PriceData,
    health_score_data: MarketHealthScore,
) -> EnrichedIndicator:
    """Enrich 10Y Treasury indicator with plain-language labels.

    Args:
        tnx_data: 10Y Treasury price data
        health_score_data: Market health score with components

    Returns:
        Enriched TNX indicator
    """
    tnx_label = plain_language.get_indicator_label("tnx")
    tnx_component = next((c for c in health_score_data.components if "Treasury" in c.name), None)

    return EnrichedIndicator(
        value=tnx_data.price,
        change_pct=None,
        label=tnx_label["label"],
        short_label=tnx_label["short"],
        tooltip=tnx_label["tooltip"],
        signal=tnx_component.signal if tnx_component else "Neutral",
        emoji=get_signal_emoji(tnx_component.signal if tnx_component else "Neutral"),
        last_updated=tnx_data.cached_at.isoformat(),
    )


def enrich_dxy_indicator(
    dxy_data: PriceData,
    health_score_data: MarketHealthScore,
) -> EnrichedIndicator:
    """Enrich US Dollar indicator with plain-language labels.

    Args:
        dxy_data: US Dollar price data
        health_score_data: Market health score with components

    Returns:
        Enriched DXY indicator
    """
    dxy_label = plain_language.get_indicator_label("dxy")
    dxy_component = next((c for c in health_score_data.components if "Dollar" in c.name), None)

    return EnrichedIndicator(
        value=dxy_data.price,
        change_pct=None,
        label=dxy_label["label"],
        short_label=dxy_label["short"],
        tooltip=dxy_label["tooltip"],
        signal=dxy_component.signal if dxy_component else "Neutral",
        emoji=get_signal_emoji(dxy_component.signal if dxy_component else "Neutral"),
        last_updated=dxy_data.cached_at.isoformat(),
    )


def group_sectors_by_performance(
    sector_data_list: list[tuple[str, float | None, float | None, str | None]],
) -> tuple[list[SectorInfo], list[SectorInfo], list[SectorInfo]]:
    """Group sectors into Leading/Neutral/Lagging categories based on performance.

    Args:
        sector_data_list: List of tuples (symbol, price, change_pct, timestamp)

    Returns:
        Tuple of (leading_sectors, neutral_sectors, lagging_sectors)
    """
    # Filter sectors with valid change_pct and sort by performance
    sectors_with_change = [
        (symbol, price, change_pct, timestamp)
        for symbol, price, change_pct, timestamp in sector_data_list
        if change_pct is not None
    ]
    sectors_with_change.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)

    # Calculate thresholds (top 33%, middle 34%, bottom 33%)
    total_count = len(sectors_with_change)
    leading_cutoff = int(total_count * 0.33)
    lagging_start = int(total_count * 0.67)

    leading_sectors: list[SectorInfo] = []
    neutral_sectors: list[SectorInfo] = []
    lagging_sectors: list[SectorInfo] = []

    for idx, (symbol, price, change_pct, timestamp) in enumerate(sectors_with_change):
        sector_label = plain_language.get_sector_label(symbol)

        sector_info = SectorInfo(
            symbol=symbol,
            name=sector_label["name"],
            description=sector_label["description"],
            price=price,
            change_pct=change_pct,
            signal="Leading"
            if idx < leading_cutoff
            else ("Lagging" if idx >= lagging_start else "Neutral"),
            last_updated=timestamp,
        )

        if idx < leading_cutoff:
            leading_sectors.append(sector_info)
        elif idx >= lagging_start:
            lagging_sectors.append(sector_info)
        else:
            neutral_sectors.append(sector_info)

    return leading_sectors, neutral_sectors, lagging_sectors

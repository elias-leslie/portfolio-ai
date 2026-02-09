"""Watchlist Discovery Module.

Discovers high-potential symbols from top gainers, volume spikes, and news mentions.
Scheduled via Hatchet cron: Daily 08:00 UTC
"""

from __future__ import annotations

from typing import Any

from ...logging_config import get_logger
from ...rules.loader import get_rules
from ...storage import PortfolioStorage
from .helpers import (
    add_symbol_to_watchlist,
    calculate_discovery_score,
    get_existing_watchlist_symbols,
    get_news_mentions,
    get_top_gainers,
    get_volume_spikes,
    get_watchlist_size,
)

logger = get_logger(__name__)


# =============================================================================
# =============================================================================


def discover_watchlist_candidates_task() -> dict[str, Any]:
    """Discover and add high-potential symbols to watchlist.

    Scheduled: Daily 08:00 UTC
    Limits: Max 5 additions per day, respects max watchlist size
    """
    rules = get_rules()
    wm = rules.watchlist_management

    storage = PortfolioStorage()
    try:
        # Check current size
        current_size = get_watchlist_size(storage)
        if current_size >= wm.max_watchlist_size:
            logger.info(
                "watchlist_discovery_skipped",
                reason="watchlist_full",
                current_size=current_size,
                max_size=wm.max_watchlist_size,
            )
            return {
                "status": "skipped",
                "reason": "watchlist_full",
                "current_size": current_size,
            }

        # Get discovery data
        gainers = get_top_gainers(storage, wm.gainers_threshold_pct)
        volume_spikes = get_volume_spikes(storage, wm.volume_spike_ratio)
        news_mentions = get_news_mentions(storage, wm.news_mention_threshold)

        # Get existing symbols
        existing = get_existing_watchlist_symbols(storage)

        # Find all unique candidates
        all_symbols: set[str] = set()
        for g in gainers:
            all_symbols.add(g["symbol"])
        for v in volume_spikes:
            all_symbols.add(v["symbol"])
        for n in news_mentions:
            all_symbols.add(n["symbol"])

        # Filter out existing
        candidates = all_symbols - existing

        # Score candidates
        scored_candidates: list[dict[str, Any]] = []
        for symbol in candidates:
            score = calculate_discovery_score(symbol, gainers, volume_spikes, news_mentions)
            if score >= wm.discovery_score_threshold:
                scored_candidates.append({"symbol": symbol, "score": score})

        # Sort by score and limit
        scored_candidates.sort(key=lambda x: float(x["score"]), reverse=True)
        to_add = scored_candidates[: wm.max_daily_additions]

        # Respect watchlist size limit
        slots_available = wm.max_watchlist_size - current_size
        to_add = to_add[:slots_available]

        # Add to watchlist
        added: list[dict[str, Any]] = []
        for candidate in to_add:
            item_id = add_symbol_to_watchlist(
                storage,
                candidate["symbol"],
                float(candidate["score"]),
            )
            if item_id:
                added.append({"symbol": candidate["symbol"], "score": candidate["score"]})

        logger.info(
            "watchlist_discovery_complete",
            candidates_found=len(candidates),
            qualified=len(scored_candidates),
            added=len(added),
        )

        return {
            "status": "success",
            "candidates_found": len(candidates),
            "qualified": len(scored_candidates),
            "added": added,
            "top_gainers": len(gainers),
            "volume_spikes": len(volume_spikes),
            "news_mentions": len(news_mentions),
        }

    except Exception as e:
        logger.error("watchlist_discovery_failed", error=str(e))
        return {"status": "error", "error": str(e)}

"use client";

import type { WatchlistItem } from "@/lib/api/watchlist";

interface ExpandedRowNarrativeProps {
    item: WatchlistItem;
}

/**
 * ExpandedRowNarrative - DEPRECATED
 *
 * Previously displayed "Trading Intelligence" card with:
 * - Signal badge (BUY/HOLD/AVOID)
 * - Trading style
 * - Trade levels (Entry/Stop/Target)
 * - Position sizing
 * - "Why This Works" narrative
 *
 * Removed per plan: Watchlist/Picks Architecture Rationalization
 * - Signal/style/trade levels are PREMATURE before thesis validation
 * - Thesis section now handles investment reasoning
 * - Trade recommendations moved to Picks page (requires validation)
 *
 * Component kept for backward compatibility but returns null.
 */
export function ExpandedRowNarrative({ item: _item }: ExpandedRowNarrativeProps) {
    return null;
}

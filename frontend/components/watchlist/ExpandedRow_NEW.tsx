"use client";

/**
 * Expanded row display for watchlist items
 *
 * This is the main container that assembles all watchlist detail components:
 * - Refresh status indicator
 * - Narrative intelligence (trading signals, action plans)
 * - News intelligence card
 * - Score breakdown (Price + Technical)
 * - Notes editing
 *
 * Refactored from 1,142-line monolithic component into focused subcomponents.
 */

import { usePreferences } from "@/lib/hooks/usePreferences";
import { useNewsIntelligence } from "@/lib/hooks/useNews";
import type { WatchlistItem, RefreshStatus } from "@/lib/api/watchlist";
import { UnifiedNewsIntelligenceCard } from "@/components/shared/UnifiedNewsIntelligenceCard";
import { ExpandedRowRefreshStatus } from "./ExpandedRowRefreshStatus";
import { ExpandedRowNarrative } from "./ExpandedRowNarrative";
import { ExpandedRowScoreBreakdown } from "./ExpandedRowScoreBreakdown";
import { ExpandedRowNotes } from "./ExpandedRowNotes";

interface ExpandedRowProps {
    item: WatchlistItem;
    refreshStatus?: RefreshStatus;
}

export function ExpandedRow({ item, refreshStatus }: ExpandedRowProps) {
    const { data: preferences } = usePreferences();
    const { data: fullNewsData } = useNewsIntelligence(item.symbol, { limit: 50 });

    const userTimezone = preferences?.display_timezone ?? "America/New_York";
    const showNews = preferences?.watchlist_show_news ?? true;
    const newsHidden = preferences?.watchlist_show_news === false;

    return (
        <div className="space-y-4">
            {/* Refresh Progress */}
            {refreshStatus && (
                <ExpandedRowRefreshStatus
                    refreshStatus={refreshStatus}
                    symbol={item.symbol}
                />
            )}

            {/* Narrative Intelligence */}
            <ExpandedRowNarrative item={item} />

            {/* News Intelligence */}
            <UnifiedNewsIntelligenceCard
                symbol={item.symbol}
                newsData={fullNewsData}
                showNews={showNews}
                newsHidden={newsHidden}
            />

            {/* Score Breakdown */}
            <ExpandedRowScoreBreakdown
                item={item}
                userTimezone={userTimezone}
            />

            {/* Notes */}
            <ExpandedRowNotes item={item} />
        </div>
    );
}

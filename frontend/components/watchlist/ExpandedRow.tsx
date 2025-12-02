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
import { Button } from "@/components/ui/button";
import { Bot, BarChart3, ExternalLink } from "lucide-react";
import { useGenerateStrategy } from "@/lib/hooks/useStrategies";
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
    const generateStrategy = useGenerateStrategy();

    const userTimezone = preferences?.display_timezone ?? "America/New_York";
    const newsHidden = preferences?.watchlist_show_news === false;

    const handleRunAgent = () => {
        generateStrategy.mutate({ symbol: item.symbol });
    };

    const handleRunBacktest = () => {
        window.location.href = `/backtest?ticker=${item.symbol}`;
    };

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

            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2">
                <Button
                    variant="default"
                    size="sm"
                    onClick={handleRunAgent}
                    disabled={generateStrategy.isPending}
                >
                    <Bot className="mr-2 h-4 w-4" />
                    {generateStrategy.isPending ? "Generating..." : "Run AI Agent"}
                </Button>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRunBacktest}
                >
                    <BarChart3 className="mr-2 h-4 w-4" />
                    Backtest
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => window.location.href = `/strategies?symbol=${item.symbol}`}
                >
                    <ExternalLink className="mr-2 h-4 w-4" />
                    View Strategies
                </Button>
            </div>

            {/* News Intelligence */}
            <UnifiedNewsIntelligenceCard
                ticker={item.symbol}
                marketNewsData={fullNewsData ?? undefined}
                newsHidden={newsHidden}
                showSentimentBreakdown
                title="News & Sentiment"
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

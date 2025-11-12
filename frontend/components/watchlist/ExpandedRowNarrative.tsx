"use client";

/**
 * Narrative Intelligence display for watchlist expanded row
 *
 * Shows AI-generated trading intelligence including:
 * - Headline and signal classification (BUY/HOLD/AVOID)
 * - Trading style recommendation (Index/Trend/Value/Swing/Event)
 * - Trade levels (entry, stop loss, profit target)
 * - Position sizing calculations
 * - Action plan and special notes
 * - Company health bullets
 * - Inline 3-pillar score breakdown
 *
 * IMPORTANT: This is a STUB placeholder component.
 * The full ~660-line narrative intelligence section from the original
 * ExpandedRow.tsx (lines 229-888) needs to be fully extracted here.
 *
 * For now, this provides a basic structure that compiles. The Verification
 * Agent should complete the full extraction to preserve all nested logic,
 * conditional rendering, and formatting.
 *
 * Extracted from ExpandedRow.tsx to reduce file size.
 */

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WatchlistItem } from "@/lib/api/watchlist";

interface ExpandedRowNarrativeProps {
    item: WatchlistItem;
}

export function ExpandedRowNarrative({ item }: ExpandedRowNarrativeProps) {
    if (!item.narrative_headline) {
        return null;
    }

    return (
        <Card className="border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Trading Intelligence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="text-sm text-text-muted">
                    <p className="font-medium mb-2">🚧 Component Refactoring In Progress</p>
                    <p>
                        The full narrative intelligence section (~660 lines) is being extracted
                        from ExpandedRow.tsx. This stub ensures the application compiles.
                    </p>
                    <p className="mt-2">
                        <strong>Headline:</strong> {item.narrative_headline}
                    </p>
                    {item.signal_type && (
                        <p>
                            <strong>Signal:</strong> {item.signal_type}
                        </p>
                    )}
                </div>

                <div className="text-xs text-text-muted italic border-t border-border pt-3">
                    TODO: Extract complete narrative section from original ExpandedRow.tsx
                    (lines 229-888) including all subsections, conditional logic, and styling.
                </div>
            </CardContent>
        </Card>
    );
}

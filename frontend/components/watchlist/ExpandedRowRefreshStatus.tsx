"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Loader2 } from "lucide-react";
import type { RefreshStatus } from "@/lib/api/watchlist";

interface ExpandedRowRefreshStatusProps {
    refreshStatus: RefreshStatus;
    symbol: string;
}

/**
 * Refresh progress indicator for watchlist expanded row
 *
 * Displays real-time progress when a watchlist item is being refreshed:
 * - Elapsed time
 * - Progress percentage
 * - Items processed count
 *
 * Extracted from ExpandedRow.tsx to reduce file size.
 */
export function ExpandedRowRefreshStatus({
    refreshStatus,
    symbol,
}: ExpandedRowRefreshStatusProps) {
    const isRefreshing =
        refreshStatus.is_refreshing && refreshStatus.current_symbol === symbol;

    if (!isRefreshing) {
        return null;
    }

    return (
        <Card className="border-accent bg-accent/5">
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Refreshing Scores...
                </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
                <div className="text-sm text-text-muted">
                    {refreshStatus.elapsed_seconds !== undefined && (
                        <p>
                            Elapsed time:{" "}
                            <span className="font-medium text-text">
                                {refreshStatus.elapsed_seconds}s
                            </span>
                        </p>
                    )}
                    {refreshStatus.percent_complete !== undefined && (
                        <p>
                            Progress:{" "}
                            <span className="font-medium text-text">
                                {refreshStatus.percent_complete.toFixed(0)}%
                            </span>
                        </p>
                    )}
                    {refreshStatus.processed_items !== undefined &&
                        refreshStatus.total_items !== undefined && (
                            <p>
                                Items processed:{" "}
                                <span className="font-medium text-text">
                                    {refreshStatus.processed_items} /{" "}
                                    {refreshStatus.total_items}
                                </span>
                            </p>
                        )}
                </div>
            </CardContent>
        </Card>
    );
}

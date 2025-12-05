"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { WatchlistItem } from "@/lib/api/watchlist";
import { getScoreBadgeVariant, formatTimestamp } from "./ExpandedRowUtils";

interface ExpandedRowScoreBreakdownProps {
    item: WatchlistItem;
    userTimezone: string;
}

/**
 * Score breakdown cards for watchlist expanded row
 *
 * Displays detailed score breakdown for:
 * - Price Score - Price momentum and volatility metrics
 * - Technical Score - Technical indicator metrics
 * - Fundamental Score - Financial health metrics (optional)
 * - Catalyst Score - News sentiment and events (optional)
 *
 * Each card shows:
 * - Overall score with color-coded badge
 * - Weight in overall calculation
 * - Last updated timestamp
 * - Detailed metrics breakdown
 * - Stale indicator if data is outdated
 *
 * Extracted from ExpandedRow.tsx to reduce file size.
 */
export function ExpandedRowScoreBreakdown({
    item,
    userTimezone,
}: ExpandedRowScoreBreakdownProps) {
    const hasScore = !!item.current_score;
    const priceScore = item.current_score?.price;
    const techScore = item.current_score?.technical;
    const fundamentalScore = item.current_score?.fundamental;
    const catalystScore = item.current_score?.catalyst;

    if (!hasScore) {
        return null;
    }

    // Count how many pillars we have to display
    const pillarCount = [priceScore, techScore, fundamentalScore, catalystScore].filter(Boolean).length;
    const gridCols = pillarCount === 4 ? "sm:grid-cols-2 lg:grid-cols-4" : "sm:grid-cols-2";

    return (
        <div className={`grid gap-4 ${gridCols}`}>
            {/* Price Score Card */}
            <Card className="border-border">
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center justify-between">
                        Price Score
                        {priceScore?.stale && (
                            <Badge
                                variant="outline"
                                className="text-xs font-normal"
                            >
                                Stale
                            </Badge>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div>
                        <Badge
                            variant={getScoreBadgeVariant(
                                priceScore?.score ?? 0,
                            )}
                        >
                            {priceScore?.score.toFixed(1) ?? "—"}
                        </Badge>
                        <p className="mt-2 text-xs text-text-muted">
                            Weight:{" "}
                            {((priceScore?.weight ?? 0) * 100).toFixed(0)}%
                        </p>
                    </div>
                    {priceScore?.updated_at && (
                        <p className="text-xs text-text-muted">
                            Updated:{" "}
                            {formatTimestamp(
                                priceScore.updated_at,
                                userTimezone,
                            )}
                        </p>
                    )}
                    {priceScore?.metadata &&
                        Object.keys(priceScore.metadata).length > 0 && (
                            <div className="space-y-1 text-xs">
                                <p className="font-medium text-text">
                                    Metrics:
                                </p>
                                {Object.entries(priceScore.metadata).map(
                                    ([key, value]) => (
                                        <p
                                            key={key}
                                            className="text-text-muted"
                                        >
                                            {key}:{" "}
                                            {typeof value === "number"
                                                ? value.toFixed(2)
                                                : String(value)}
                                        </p>
                                    ),
                                )}
                            </div>
                        )}
                </CardContent>
            </Card>

            {/* Technical Score Card */}
            <Card className="border-border">
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center justify-between">
                        Technical Score
                        {techScore?.stale && (
                            <Badge
                                variant="outline"
                                className="text-xs font-normal"
                            >
                                Stale
                            </Badge>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div>
                        <Badge
                            variant={getScoreBadgeVariant(
                                techScore?.score ?? 0,
                            )}
                        >
                            {techScore?.score.toFixed(1) ?? "—"}
                        </Badge>
                        <p className="mt-2 text-xs text-text-muted">
                            Weight:{" "}
                            {((techScore?.weight ?? 0) * 100).toFixed(0)}%
                        </p>
                    </div>
                    {techScore?.updated_at && (
                        <p className="text-xs text-text-muted">
                            Updated:{" "}
                            {formatTimestamp(
                                techScore.updated_at,
                                userTimezone,
                            )}
                        </p>
                    )}
                    {techScore?.metadata &&
                        Object.keys(techScore.metadata).length > 0 && (
                            <div className="space-y-1 text-xs">
                                <p className="font-medium text-text">Metrics:</p>
                                {Object.entries(techScore.metadata).map(
                                    ([key, value]) => (
                                        <p
                                            key={key}
                                            className="text-text-muted"
                                        >
                                            {key}:{" "}
                                            {typeof value === "number"
                                                ? value.toFixed(2)
                                                : String(value)}
                                        </p>
                                    ),
                                )}
                            </div>
                        )}
                </CardContent>
            </Card>

            {/* Fundamental Score Card */}
            {fundamentalScore && (
                <Card className="border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center justify-between">
                            Fundamental Score
                            {fundamentalScore.stale && (
                                <Badge
                                    variant="outline"
                                    className="text-xs font-normal"
                                >
                                    Stale
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div>
                            <Badge
                                variant={getScoreBadgeVariant(
                                    fundamentalScore.score,
                                )}
                            >
                                {fundamentalScore.score.toFixed(1)}
                            </Badge>
                            <p className="mt-2 text-xs text-text-muted">
                                Weight:{" "}
                                {(fundamentalScore.weight * 100).toFixed(0)}%
                            </p>
                        </div>
                        {fundamentalScore.updated_at && (
                            <p className="text-xs text-text-muted">
                                Updated:{" "}
                                {formatTimestamp(
                                    fundamentalScore.updated_at,
                                    userTimezone,
                                )}
                            </p>
                        )}
                        {fundamentalScore.metadata &&
                            Object.keys(fundamentalScore.metadata).length > 0 && (
                                <div className="space-y-1 text-xs">
                                    <p className="font-medium text-text">Metrics:</p>
                                    {Object.entries(fundamentalScore.metadata).map(
                                        ([key, value]) => (
                                            <p
                                                key={key}
                                                className="text-text-muted"
                                            >
                                                {key}:{" "}
                                                {typeof value === "number"
                                                    ? value.toFixed(2)
                                                    : String(value)}
                                            </p>
                                        ),
                                    )}
                                </div>
                            )}
                    </CardContent>
                </Card>
            )}

            {/* Catalyst Score Card */}
            {catalystScore && (
                <Card className="border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base flex items-center justify-between">
                            Catalyst Score
                            {catalystScore.stale && (
                                <Badge
                                    variant="outline"
                                    className="text-xs font-normal"
                                >
                                    Stale
                                </Badge>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div>
                            <Badge
                                variant={getScoreBadgeVariant(
                                    catalystScore.score,
                                )}
                            >
                                {catalystScore.score.toFixed(1)}
                            </Badge>
                            <p className="mt-2 text-xs text-text-muted">
                                Weight:{" "}
                                {(catalystScore.weight * 100).toFixed(0)}%
                            </p>
                        </div>
                        {catalystScore.updated_at && (
                            <p className="text-xs text-text-muted">
                                Updated:{" "}
                                {formatTimestamp(
                                    catalystScore.updated_at,
                                    userTimezone,
                                )}
                            </p>
                        )}
                        {catalystScore.metadata &&
                            Object.keys(catalystScore.metadata).length > 0 && (
                                <div className="space-y-1 text-xs">
                                    <p className="font-medium text-text">Metrics:</p>
                                    {Object.entries(catalystScore.metadata).map(
                                        ([key, value]) => (
                                            <p
                                                key={key}
                                                className="text-text-muted"
                                            >
                                                {key}:{" "}
                                                {typeof value === "number"
                                                    ? value.toFixed(2)
                                                    : String(value)}
                                            </p>
                                        ),
                                    )}
                                </div>
                            )}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

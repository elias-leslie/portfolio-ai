"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
// TEMPORARILY DISABLED: Sparkline - re-enable after 90 days of data
// import { Sparkline } from "@/components/ui/sparkline";
import {
    Save,
    Edit2,
    X,
    Loader2,
    TrendingUp,
    TrendingDown,
    ExternalLink,
} from "lucide-react";
// TEMPORARILY DISABLED: Score history - re-enable with sparklines
// import { useUpdateWatchlistItem, useScoreHistory } from "@/lib/hooks/useWatchlist";
import { useUpdateWatchlistItem } from "@/lib/hooks/useWatchlist";
import { usePreferences } from "@/lib/hooks/usePreferences";
import { useNewsIntelligence } from "@/lib/hooks/useNews";
import { toast } from "sonner";
import type { WatchlistItem, RefreshStatus } from "@/lib/api/watchlist";
import {
    formatSentimentScore,
    formatVendorLabel,
    getSentimentBadgeVariant,
    formatConfidence,
} from "@/lib/utils/news-formatting";
import { UnifiedNewsIntelligenceCard } from "@/components/shared/UnifiedNewsIntelligenceCard";

function sanitizeText(input?: string | null): string {
    if (!input) return "";
    const value = input.trim();
    if (!value) return "";
    try {
        if (
            typeof window !== "undefined" &&
            typeof window.DOMParser !== "undefined"
        ) {
            const parser = new window.DOMParser();
            const doc = parser.parseFromString(value, "text/html");
            return (doc.body?.textContent ?? "").replace(/\s+/g, " ").trim();
        }
    } catch {
        // fallthrough to regex
    }
    return value
        .replace(/<[^>]*>/g, " ")
        .replace(/\s+/g, " ")
        .trim();
}

interface ExpandedRowProps {
    item: WatchlistItem;
    refreshStatus?: RefreshStatus;
}

export function ExpandedRow({ item, refreshStatus }: ExpandedRowProps) {
    const [isEditingNote, setIsEditingNote] = useState(false);
    const [noteValue, setNoteValue] = useState(item.note || "");
    const updateMutation = useUpdateWatchlistItem();
    // TEMPORARILY DISABLED: Score history - re-enable with sparklines
    // const { data: historyResponse } = useScoreHistory(item.id);
    const { data: preferences } = usePreferences();

    // Fetch full news intelligence (50 articles) for this ticker
    const { data: fullNewsData } = useNewsIntelligence(item.symbol, { limit: 50 });

    const hasScore = !!item.current_score;
    // const history = historyResponse?.history || [];
    const priceScore = item.current_score?.price;
    const techScore = item.current_score?.technical;
    const showNews = preferences?.watchlist_show_news ?? true;
    const newsHidden = preferences?.watchlist_show_news === false;
    const newsSummary = item.recent_news?.summary;
    const newsArticles = item.recent_news?.articles ?? [];
    const totalModelCoverage =
        newsSummary && newsSummary.model_breakdown
            ? Object.values(newsSummary.model_breakdown).reduce(
                  (sum, value) => sum + value,
                  0,
              )
            : 0;
    const finbertCoverage = newsSummary?.model_breakdown?.finbert ?? 0;
    const fallbackCoverage = Math.max(totalModelCoverage - finbertCoverage, 0);
    const maxNewsArticles = Math.min(newsArticles.length, 5);

    // Check if this item is currently being refreshed
    const isRefreshing =
        refreshStatus?.is_refreshing &&
        refreshStatus.current_symbol === item.symbol;

    const handleSaveNote = () => {
        updateMutation.mutate(
            {
                itemId: item.id,
                data: { note: noteValue.trim() || undefined },
            },
            {
                onSuccess: () => {
                    toast.success("Note updated");
                    setIsEditingNote(false);
                },
                onError: (error) => {
                    toast.error(`Failed to update note: ${error.message}`);
                },
            },
        );
    };

    const handleCancelEdit = () => {
        setNoteValue(item.note || "");
        setIsEditingNote(false);
    };

    const formatScoreChange = (change?: number | null) => {
        if (change === null || change === undefined || Number.isNaN(change)) {
            return null;
        }
        const formatted = change.toFixed(2);
        return change >= 0 ? `+${formatted}` : formatted;
    };

    const formatModelCoverage = () => {
        if (totalModelCoverage === 0) {
            return "No articles scored";
        }
        if (finbertCoverage === totalModelCoverage) {
            return "FinBERT coverage";
        }
        if (finbertCoverage === 0) {
            return "Fallback sentiment (VADER)";
        }
        return `FinBERT ${finbertCoverage}/${totalModelCoverage}`;
    };

    // Get score badge variant
    const getScoreBadgeVariant = (
        score: number,
    ): "viz-0" | "viz-1" | "viz-2" | "viz-3" | "viz-4" | "viz-5" => {
        if (score >= 80) return "viz-5";
        if (score >= 60) return "viz-4";
        if (score >= 40) return "viz-3";
        if (score >= 20) return "viz-2";
        if (score >= 10) return "viz-1";
        return "viz-0";
    };

    // Get user's timezone preference
    const userTimezone = preferences?.display_timezone ?? "America/New_York";

    // Get timezone abbreviation (EST, PST, etc.)
    const getTimezoneAbbreviation = (timezone: string): string => {
        const date = new Date();
        const formatter = new Intl.DateTimeFormat("en-US", {
            timeZone: timezone,
            timeZoneName: "short",
        });
        const parts = formatter.formatToParts(date);
        const timeZonePart = parts.find((part) => part.type === "timeZoneName");
        return timeZonePart?.value ?? "";
    };

    // Format timestamp with user's timezone
    const formatTimestamp = (timestamp?: string) => {
        if (!timestamp) return "Never";
        const date = new Date(timestamp);
        const formatted = date.toLocaleString("en-US", {
            timeZone: userTimezone,
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
        });
        const tzAbbr = getTimezoneAbbreviation(userTimezone);
        return `${formatted} ${tzAbbr}`;
    };

    return (
        <div className="space-y-4">
            {/* Refresh Progress Card */}
            {isRefreshing && refreshStatus && (
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
                                        {refreshStatus.percent_complete.toFixed(
                                            0,
                                        )}
                                        %
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
            )}

            {/* Narrative Intelligence Section */}
            {item.narrative_headline && (
                <Card className="border-border">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">
                            Trading Intelligence
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Headline */}
                        <div>
                            <h4 className="text-sm font-semibold text-text mb-2">
                                {item.narrative_headline}
                            </h4>
                        </div>

                        {/* Signal + Style Row */}
                        <div className="flex flex-wrap items-center gap-3">
                            {item.signal_type && (
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-text-muted">
                                        Signal:
                                    </span>
                                    {(() => {
                                        const getSignalDisplay = (
                                            signalType:
                                                | "BUY"
                                                | "HOLD"
                                                | "AVOID",
                                        ) => {
                                            switch (signalType) {
                                                case "BUY":
                                                    return {
                                                        icon: "🟢",
                                                        color: "bg-green-500/10 text-green-600 border-green-500/20",
                                                        label: "BUY",
                                                    };
                                                case "HOLD":
                                                    return {
                                                        icon: "🟡",
                                                        color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
                                                        label: "HOLD",
                                                    };
                                                case "AVOID":
                                                    return {
                                                        icon: "🔴",
                                                        color: "bg-red-500/10 text-red-600 border-red-500/20",
                                                        label: "AVOID",
                                                    };
                                            }
                                        };
                                        const signalDisplay = getSignalDisplay(
                                            item.signal_type,
                                        );
                                        return (
                                            <div
                                                className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold ${signalDisplay.color}`}
                                            >
                                                <span>
                                                    {signalDisplay.icon}
                                                </span>
                                                <span>
                                                    {signalDisplay.label}
                                                </span>
                                                {item.signal_strength !==
                                                    null &&
                                                    item.signal_strength !==
                                                        undefined && (
                                                        <span className="ml-1 text-xs opacity-75">
                                                            {
                                                                item.signal_strength
                                                            }
                                                            /10
                                                        </span>
                                                    )}
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}

                            {item.recommended_style && (
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-text-muted">
                                        Style:
                                    </span>
                                    {(() => {
                                        const getStyleDisplay = (
                                            style:
                                                | "Index"
                                                | "Trend"
                                                | "Value"
                                                | "Swing"
                                                | "Event",
                                        ) => {
                                            switch (style) {
                                                case "Index":
                                                    return {
                                                        icon: "📈",
                                                        color: "bg-blue-500/10 text-blue-600 border-blue-500/20",
                                                    };
                                                case "Trend":
                                                    return {
                                                        icon: "🔥",
                                                        color: "bg-orange-500/10 text-orange-600 border-orange-500/20",
                                                    };
                                                case "Value":
                                                    return {
                                                        icon: "💎",
                                                        color: "bg-purple-500/10 text-purple-600 border-purple-500/20",
                                                    };
                                                case "Swing":
                                                    return {
                                                        icon: "⚡",
                                                        color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
                                                    };
                                                case "Event":
                                                    return {
                                                        icon: "📅",
                                                        color: "bg-red-500/10 text-red-600 border-red-500/20",
                                                    };
                                            }
                                        };
                                        const styleDisplay = getStyleDisplay(
                                            item.recommended_style,
                                        );
                                        return (
                                            <div
                                                className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold ${styleDisplay.color}`}
                                                title={`${item.optimal_holding_period ?? ""} | ${item.risk_level ?? ""} risk`}
                                            >
                                                <span>{styleDisplay.icon}</span>
                                                <span>
                                                    {item.recommended_style}
                                                </span>
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}

                            {item.optimal_holding_period && (
                                <div className="text-xs text-text-muted">
                                    Hold:{" "}
                                    <span className="font-medium text-text">
                                        {item.optimal_holding_period}
                                    </span>
                                </div>
                            )}

                            {item.risk_level && (
                                <div className="text-xs text-text-muted">
                                    Risk:{" "}
                                    <span className="font-medium text-text">
                                        {item.risk_level}
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Trade Levels (Entry/Stop/Target) */}
                        {(item.entry_price !== null &&
                            item.entry_price !== undefined) ||
                        (item.stop_loss !== null &&
                            item.stop_loss !== undefined) ||
                        (item.profit_target !== null &&
                            item.profit_target !== undefined) ? (
                            <div className="border-t border-border pt-3">
                                <h5 className="text-xs font-semibold text-text mb-2">
                                    Trade Levels
                                </h5>
                                <div className="grid grid-cols-3 gap-3 text-xs">
                                    {item.entry_price !== null &&
                                        item.entry_price !== undefined && (
                                            <div>
                                                <p className="text-text-muted">
                                                    Entry
                                                </p>
                                                <p className="font-semibold text-green-600">
                                                    $
                                                    {item.entry_price.toFixed(
                                                        2,
                                                    )}
                                                </p>
                                            </div>
                                        )}
                                    {item.stop_loss !== null &&
                                        item.stop_loss !== undefined && (
                                            <div>
                                                <p className="text-text-muted">
                                                    Stop
                                                </p>
                                                <p className="font-semibold text-red-600">
                                                    ${item.stop_loss.toFixed(2)}
                                                </p>
                                            </div>
                                        )}
                                    {item.profit_target !== null &&
                                        item.profit_target !== undefined && (
                                            <div>
                                                <p className="text-text-muted">
                                                    Target
                                                </p>
                                                <p className="font-semibold text-blue-600">
                                                    $
                                                    {item.profit_target.toFixed(
                                                        2,
                                                    )}
                                                </p>
                                                {item.entry_price !== null &&
                                                    item.entry_price !==
                                                        undefined && (
                                                        <p className="text-text-muted mt-0.5">
                                                            +
                                                            {(
                                                                ((item.profit_target -
                                                                    item.entry_price) /
                                                                    item.entry_price) *
                                                                100
                                                            ).toFixed(1)}
                                                            %
                                                        </p>
                                                    )}
                                            </div>
                                        )}
                                </div>
                            </div>
                        ) : null}

                        {/* Position Sizing */}
                        {item.position_size_shares !== null &&
                            item.position_size_shares !== undefined &&
                            item.position_size_shares > 0 && (
                                <div className="border-t border-border pt-3">
                                    <h5 className="text-xs font-semibold text-text mb-2">
                                        Position Sizing
                                    </h5>
                                    <div className="grid grid-cols-2 gap-3 text-xs">
                                        <div>
                                            <p className="text-text-muted">
                                                Shares
                                            </p>
                                            <p className="font-semibold text-text">
                                                {item.position_size_shares}{" "}
                                                shares
                                            </p>
                                        </div>
                                        {item.entry_price !== null &&
                                            item.entry_price !== undefined && (
                                                <div>
                                                    <p className="text-text-muted">
                                                        Investment
                                                    </p>
                                                    <p className="font-semibold text-text">
                                                        $
                                                        {(
                                                            item.position_size_shares *
                                                            item.entry_price
                                                        ).toFixed(2)}
                                                    </p>
                                                </div>
                                            )}
                                    </div>
                                </div>
                            )}

                        {/* Special Notes & Warnings */}
                        <div className="border-t border-border pt-3 space-y-2">
                            {/* Earnings Warning (if available) */}
                            {/* Note: Backend doesn't populate earnings_date yet, but UI is ready for when it does */}

                            {/* Why This Works - Signal-based explanation */}
                            {item.signal_type && (
                                <div className="text-xs">
                                    <p className="font-semibold text-text mb-1 flex items-center gap-1">
                                        <span>💡</span>
                                        <span>WHY THIS WORKS:</span>
                                    </p>
                                    <p className="text-text-muted leading-relaxed">
                                        {item.signal_type === "BUY" && (
                                            <>
                                                Technical setup shows{" "}
                                                {item.signal_strength !==
                                                    null &&
                                                item.signal_strength !==
                                                    undefined &&
                                                item.signal_strength >= 7
                                                    ? "strong"
                                                    : "positive"}{" "}
                                                momentum with{" "}
                                                {item.recommended_style ===
                                                "Trend"
                                                    ? "trend-following characteristics"
                                                    : item.recommended_style ===
                                                        "Value"
                                                      ? "value opportunity"
                                                      : item.recommended_style ===
                                                          "Swing"
                                                        ? "reversal potential"
                                                        : item.recommended_style ===
                                                            "Event"
                                                          ? "catalyst-driven setup"
                                                          : "favorable conditions"}
                                                .
                                                {item.signal_strength !==
                                                    null &&
                                                    item.signal_strength !==
                                                        undefined &&
                                                    item.signal_strength >= 8 &&
                                                    " Multiple confirming indicators align for high-probability setup."}
                                            </>
                                        )}
                                        {item.signal_type === "HOLD" && (
                                            <>
                                                Mixed signals suggest waiting
                                                for clearer setup.{" "}
                                                {item.recommended_style ===
                                                    "Value" &&
                                                    "Quality company but timing not optimal yet. "}
                                                Monitor for improvement in
                                                technical indicators before
                                                committing capital.
                                            </>
                                        )}
                                        {item.signal_type === "AVOID" && (
                                            <>
                                                Technical indicators show{" "}
                                                {item.signal_strength !==
                                                    null &&
                                                item.signal_strength !==
                                                    undefined &&
                                                item.signal_strength <= 3
                                                    ? "significant"
                                                    : ""}{" "}
                                                weakness. Risk outweighs
                                                potential reward at current
                                                levels. Wait for stabilization
                                                and trend reversal confirmation.
                                            </>
                                        )}
                                    </p>
                                </div>
                            )}

                            {/* Score Breakdown (3-Pillar) */}
                            {hasScore && (
                                <div className="border-t border-border pt-3">
                                    <h5 className="text-xs font-semibold text-text mb-3">
                                        📊 Score Breakdown
                                    </h5>
                                    <div className="space-y-2">
                                        {/* Overall Score */}
                                        <div>
                                            <div className="flex items-center justify-between text-sm mb-1">
                                                <span className="text-text-muted">
                                                    Overall
                                                </span>
                                                <span className="font-bold text-text">
                                                    {item.current_score?.overall.toFixed(
                                                        0,
                                                    )}
                                                </span>
                                            </div>
                                            <div className="h-2 bg-surface-muted rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-primary"
                                                    style={{
                                                        width: `${item.current_score?.overall || 0}%`,
                                                    }}
                                                />
                                            </div>
                                        </div>

                                        {/* Price Component */}
                                        {priceScore && (
                                            <div>
                                                <div className="flex items-center justify-between text-xs mb-1">
                                                    <span className="text-text-muted">
                                                        💰 Price (
                                                        {(
                                                            priceScore.weight *
                                                            100
                                                        ).toFixed(0)}
                                                        %)
                                                    </span>
                                                    <span className="font-medium">
                                                        {priceScore.score.toFixed(
                                                            0,
                                                        )}
                                                    </span>
                                                </div>
                                                <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-gain"
                                                        style={{
                                                            width: `${priceScore.score}%`,
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        )}

                                        {/* Technical Component */}
                                        {techScore && (
                                            <div>
                                                <div className="flex items-center justify-between text-xs mb-1">
                                                    <span className="text-text-muted">
                                                        📊 Technical (
                                                        {(
                                                            techScore.weight *
                                                            100
                                                        ).toFixed(0)}
                                                        %)
                                                    </span>
                                                    <span className="font-medium">
                                                        {techScore.score.toFixed(
                                                            0,
                                                        )}
                                                    </span>
                                                </div>
                                                <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-primary"
                                                        style={{
                                                            width: `${techScore.score}%`,
                                                        }}
                                                    />
                                                </div>
                                                {/* Technical sub-scores */}
                                                {techScore.sub_scores && (
                                                    <div className="ml-4 mt-1 text-[10px] text-text-muted">
                                                        {Object.entries(
                                                            techScore.sub_scores,
                                                        ).map(([key, value]) => (
                                                            <div key={key}>
                                                                •{" "}
                                                                {key
                                                                    .replace(
                                                                        "_",
                                                                        " ",
                                                                    )
                                                                    .toUpperCase()}
                                                                :{" "}
                                                                {typeof value ===
                                                                "number"
                                                                    ? value.toFixed(
                                                                          1,
                                                                      )
                                                                    : value}
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Fundamental Component */}
                                        {item.current_score?.fundamental && (
                                            <div>
                                                <div className="flex items-center justify-between text-xs mb-1">
                                                    <span className="text-text-muted">
                                                        🏢 Fundamental (
                                                        {(
                                                            item.current_score
                                                                .fundamental
                                                                .weight * 100
                                                        ).toFixed(0)}
                                                        %)
                                                    </span>
                                                    <span className="font-medium">
                                                        {item.current_score.fundamental.score.toFixed(
                                                            0,
                                                        )}
                                                    </span>
                                                </div>
                                                <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-gain"
                                                        style={{
                                                            width: `${item.current_score.fundamental.score}%`,
                                                        }}
                                                    />
                                                </div>
                                                {/* Fundamental sub-scores (4-pillar) - Enhanced with context */}
                                                {item.current_score.fundamental
                                                    .sub_scores && (
                                                    <div className="ml-4 mt-1 text-[10px] text-text-muted space-y-1">
                                                        {/* Valuation */}
                                                        <div>
                                                            <div className="font-medium text-text">
                                                                • VALUATION:{" "}
                                                                {item.current_score.fundamental.sub_scores
                                                                    .valuation !==
                                                                    undefined &&
                                                                item.current_score
                                                                    .fundamental
                                                                    .sub_scores
                                                                    .valuation !==
                                                                    null
                                                                    ? Number(
                                                                          item
                                                                              .current_score
                                                                              .fundamental
                                                                              .sub_scores
                                                                              .valuation,
                                                                      ).toFixed(0)
                                                                    : "N/A"}
                                                            </div>
                                                            {/* Enhanced context from metadata */}
                                                            {item.current_score.fundamental.metadata?.pe_ratio !== undefined && item.current_score.fundamental.metadata?.pe_ratio !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    P/E: {typeof item.current_score.fundamental.metadata.pe_ratio === 'number'
                                                                        ? item.current_score.fundamental.metadata.pe_ratio.toFixed(1)
                                                                        : item.current_score.fundamental.metadata.pe_ratio}
                                                                </div>
                                                            )}
                                                            {item.current_score.fundamental.metadata?.peg_ratio !== undefined && item.current_score.fundamental.metadata?.peg_ratio !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    PEG: {typeof item.current_score.fundamental.metadata.peg_ratio === 'number'
                                                                        ? item.current_score.fundamental.metadata.peg_ratio.toFixed(2)
                                                                        : item.current_score.fundamental.metadata.peg_ratio}
                                                                </div>
                                                            )}
                                                        </div>

                                                        {/* Growth */}
                                                        <div>
                                                            <div className="font-medium text-text">
                                                                • GROWTH:{" "}
                                                                {item.current_score.fundamental.sub_scores
                                                                    .growth !==
                                                                    undefined &&
                                                                item.current_score
                                                                    .fundamental
                                                                    .sub_scores
                                                                    .growth !== null
                                                                    ? Number(
                                                                          item
                                                                              .current_score
                                                                              .fundamental
                                                                              .sub_scores
                                                                              .growth,
                                                                      ).toFixed(0)
                                                                    : "N/A"}
                                                            </div>
                                                            {/* Enhanced context from metadata */}
                                                            {item.current_score.fundamental.metadata?.revenue_growth !== undefined && item.current_score.fundamental.metadata?.revenue_growth !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    Revenue: {typeof item.current_score.fundamental.metadata.revenue_growth === 'number'
                                                                        ? `${(item.current_score.fundamental.metadata.revenue_growth * 100).toFixed(1)}%`
                                                                        : item.current_score.fundamental.metadata.revenue_growth} YoY
                                                                </div>
                                                            )}
                                                            {item.current_score.fundamental.metadata?.eps_growth !== undefined && item.current_score.fundamental.metadata?.eps_growth !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    EPS: {typeof item.current_score.fundamental.metadata.eps_growth === 'number'
                                                                        ? `${(item.current_score.fundamental.metadata.eps_growth * 100).toFixed(1)}%`
                                                                        : item.current_score.fundamental.metadata.eps_growth} YoY
                                                                </div>
                                                            )}
                                                        </div>

                                                        {/* Health */}
                                                        <div>
                                                            <div className="font-medium text-text">
                                                                • HEALTH:{" "}
                                                                {item.current_score.fundamental.sub_scores
                                                                    .health !==
                                                                    undefined &&
                                                                item.current_score
                                                                    .fundamental
                                                                    .sub_scores
                                                                    .health !== null
                                                                    ? Number(
                                                                          item
                                                                              .current_score
                                                                              .fundamental
                                                                              .sub_scores
                                                                              .health,
                                                                      ).toFixed(0)
                                                                    : "N/A"}
                                                            </div>
                                                            {/* Enhanced context from metadata */}
                                                            {item.current_score.fundamental.metadata?.gross_margin !== undefined && item.current_score.fundamental.metadata?.gross_margin !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    Gross: {typeof item.current_score.fundamental.metadata.gross_margin === 'number'
                                                                        ? `${(item.current_score.fundamental.metadata.gross_margin * 100).toFixed(1)}%`
                                                                        : item.current_score.fundamental.metadata.gross_margin}
                                                                </div>
                                                            )}
                                                            {item.current_score.fundamental.metadata?.operating_margin !== undefined && item.current_score.fundamental.metadata?.operating_margin !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    Operating: {typeof item.current_score.fundamental.metadata.operating_margin === 'number'
                                                                        ? `${(item.current_score.fundamental.metadata.operating_margin * 100).toFixed(1)}%`
                                                                        : item.current_score.fundamental.metadata.operating_margin}
                                                                </div>
                                                            )}
                                                            {item.current_score.fundamental.metadata?.roic !== undefined && item.current_score.fundamental.metadata?.roic !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    ROIC: {typeof item.current_score.fundamental.metadata.roic === 'number'
                                                                        ? `${(item.current_score.fundamental.metadata.roic * 100).toFixed(1)}%`
                                                                        : item.current_score.fundamental.metadata.roic}
                                                                </div>
                                                            )}
                                                        </div>

                                                        {/* Sentiment */}
                                                        <div>
                                                            <div className="font-medium text-text">
                                                                • SENTIMENT:{" "}
                                                                {item.current_score.fundamental.sub_scores
                                                                    .sentiment !==
                                                                    undefined &&
                                                                item.current_score
                                                                    .fundamental
                                                                    .sub_scores
                                                                    .sentiment !==
                                                                    null
                                                                    ? Number(
                                                                          item
                                                                              .current_score
                                                                              .fundamental
                                                                              .sub_scores
                                                                              .sentiment,
                                                                      ).toFixed(0)
                                                                    : "N/A"}
                                                            </div>
                                                            {/* Enhanced context from metadata */}
                                                            {item.current_score.fundamental.metadata?.institutional_ownership !== undefined && item.current_score.fundamental.metadata?.institutional_ownership !== null && (
                                                                <div className="ml-3 text-text-muted">
                                                                    Institutional: {typeof item.current_score.fundamental.metadata.institutional_ownership === 'number'
                                                                        ? `${(item.current_score.fundamental.metadata.institutional_ownership * 100).toFixed(1)}%`
                                                                        : item.current_score.fundamental.metadata.institutional_ownership}
                                                                </div>
                                                            )}
                                                            {item.current_score.fundamental.metadata?.analyst_rating && (
                                                                <div className="ml-3 text-text-muted">
                                                                    Rating: {item.current_score.fundamental.metadata.analyst_rating}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Risk Disclaimer */}
                            <div className="text-xs text-text-muted italic bg-surface-muted/20 rounded p-2">
                                ⚠️ This is automated analysis. Always do your
                                own research and consider your risk tolerance
                                before trading.
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            <UnifiedNewsIntelligenceCard
                ticker={item.symbol}
                marketNewsData={fullNewsData || undefined}
                newsHidden={newsHidden}
                showSentimentBreakdown={true}
                title="News & Sentiment"
            />

            {/* Score Breakdown */}
            {hasScore && (
                <div className="grid gap-4 sm:grid-cols-2">
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
                                    {((priceScore?.weight ?? 0) * 100).toFixed(
                                        0,
                                    )}
                                    %
                                </p>
                            </div>
                            {priceScore?.updated_at && (
                                <p className="text-xs text-text-muted">
                                    Updated:{" "}
                                    {formatTimestamp(priceScore.updated_at)}
                                </p>
                            )}
                            {priceScore?.metadata &&
                                Object.keys(priceScore.metadata).length > 0 && (
                                    <div className="space-y-1 text-xs">
                                        <p className="font-medium text-text">
                                            Metrics:
                                        </p>
                                        {Object.entries(
                                            priceScore.metadata,
                                        ).map(([key, value]) => (
                                            <p
                                                key={key}
                                                className="text-text-muted"
                                            >
                                                {key}:{" "}
                                                {typeof value === "number"
                                                    ? value.toFixed(2)
                                                    : String(value)}
                                            </p>
                                        ))}
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
                                    {((techScore?.weight ?? 0) * 100).toFixed(
                                        0,
                                    )}
                                    %
                                </p>
                            </div>
                            {techScore?.updated_at && (
                                <p className="text-xs text-text-muted">
                                    Updated:{" "}
                                    {formatTimestamp(techScore.updated_at)}
                                </p>
                            )}
                            {techScore?.metadata &&
                                Object.keys(techScore.metadata).length > 0 && (
                                    <div className="space-y-1 text-xs">
                                        <p className="font-medium text-text">
                                            Metrics:
                                        </p>
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
                </div>
            )}

            {/* TEMPORARILY DISABLED: Score history sparklines - re-enable after 90 days of data */}
            {/* {history && history.length > 0 && (
        <Card className="border-border">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">7-Day Score History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <p className="mb-2 text-xs font-medium text-text-muted">
                  Overall Score
                </p>
                <Sparkline
                  data={history
                    .map((h) => h.overall)
                    .filter((score) => typeof score === "number" && !isNaN(score))}
                  width={200}
                  height={40}
                  showDots
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <p className="mb-2 text-xs font-medium text-text-muted">
                    Price Score
                  </p>
                  <Sparkline
                    data={history
                      .map((h) => h.price_score)
                      .filter((score) => typeof score === "number" && !isNaN(score))}
                    width={150}
                    height={32}
                  />
                </div>
                <div>
                  <p className="mb-2 text-xs font-medium text-text-muted">
                    Technical Score
                  </p>
                  <Sparkline
                    data={history
                      .map((h) => h.technical_score)
                      .filter((score) => typeof score === "number" && !isNaN(score))}
                    width={150}
                    height={32}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )} */}

            {/* Notes Section */}
            <Card className="border-border">
                <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center justify-between">
                        Notes
                        {!isEditingNote && (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setIsEditingNote(true)}
                                className="h-8"
                            >
                                <Edit2 className="mr-1 h-3 w-3" />
                                Edit
                            </Button>
                        )}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {isEditingNote ? (
                        <div className="space-y-3">
                            <Input
                                value={noteValue}
                                onChange={(e) => setNoteValue(e.target.value)}
                                placeholder="Add a note about this ticker..."
                                maxLength={200}
                                className="w-full"
                                autoFocus
                            />
                            <div className="flex items-center justify-between">
                                <p className="text-xs text-text-muted">
                                    {noteValue.length}/200 characters
                                </p>
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleCancelEdit}
                                        disabled={updateMutation.isPending}
                                    >
                                        <X className="mr-1 h-3 w-3" />
                                        Cancel
                                    </Button>
                                    <Button
                                        size="sm"
                                        onClick={handleSaveNote}
                                        disabled={updateMutation.isPending}
                                    >
                                        <Save className="mr-1 h-3 w-3" />
                                        Save
                                    </Button>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <p className="text-sm text-text-muted">
                            {item.note ||
                                "No notes yet. Click Edit to add one."}
                        </p>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WatchlistItem } from "@/lib/api/watchlist";
import { getSignalDisplay, sanitizeText } from "./ExpandedRowUtils";

type RecommendedStyle = Exclude<WatchlistItem["recommended_style"], null | undefined>;
type SignalType = Exclude<WatchlistItem["signal_type"], null | undefined>;

interface ExpandedRowNarrativeProps {
    item: WatchlistItem;
}

export function ExpandedRowNarrative({ item }: ExpandedRowNarrativeProps) {
    if (!item.narrative_headline) {
        return null;
    }

    const safeHeadline = sanitizeText(item.narrative_headline);

    return (
        <Card className="border-border">
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Trading Intelligence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <h4 className="text-sm font-semibold text-text mb-2">
                    {safeHeadline}
                </h4>

                <SignalStyleRow item={item} />
                <TradeLevels item={item} />
                <PositionSizing item={item} />
                <WhyThisWorks item={item} />
            </CardContent>
        </Card>
    );
}

function SignalStyleRow({ item }: { item: WatchlistItem }) {
    const signalDisplay = item.signal_type
        ? getSignalDisplay(item.signal_type)
        : null;
    const styleDisplay = item.recommended_style
        ? getStyleDisplay(item.recommended_style)
        : null;

    if (!signalDisplay && !styleDisplay && !item.optimal_holding_period && !item.risk_level) {
        return null;
    }

    return (
        <div className="flex flex-wrap items-center gap-3">
            {signalDisplay && (
                <div className="flex items-center gap-2">
                    <span className="text-xs text-text-muted">Signal:</span>
                    <div
                        className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold ${signalDisplay.color}`}
                    >
                        <span>{signalDisplay.icon}</span>
                        <span>{signalDisplay.label}</span>
                        {isNumber(item.signal_strength) && (
                            <span className="ml-1 text-xs opacity-75">
                                {item.signal_strength}/10
                            </span>
                        )}
                    </div>
                </div>
            )}

            {styleDisplay && (
                <div className="flex items-center gap-2">
                    <span className="text-xs text-text-muted">Style:</span>
                    <div
                        className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold ${styleDisplay.color}`}
                        title={`${item.optimal_holding_period ?? ""} | ${item.risk_level ?? ""} risk`}
                    >
                        <span>{styleDisplay.icon}</span>
                        <span>{item.recommended_style}</span>
                    </div>
                </div>
            )}

            {item.optimal_holding_period && (
                <div className="text-xs text-text-muted">
                    Hold: <span className="font-medium text-text">{item.optimal_holding_period}</span>
                </div>
            )}

            {item.risk_level && (
                <div className="text-xs text-text-muted">
                    Risk: <span className="font-medium text-text">{item.risk_level}</span>
                </div>
            )}
        </div>
    );
}

function TradeLevels({ item }: { item: WatchlistItem }) {
    const entryRaw = item.entry_price;
    const stopRaw = item.stop_loss;
    const targetRaw = item.profit_target;
    const hasEntry = isNumber(entryRaw);
    const hasStop = isNumber(stopRaw);
    const hasTarget = isNumber(targetRaw);

    if (!hasEntry && !hasStop && !hasTarget) {
        return null;
    }

    const entryPrice = hasEntry ? Number(entryRaw) : null;
    const stopLoss = hasStop ? Number(stopRaw) : null;
    const profitTarget = hasTarget ? Number(targetRaw) : null;
    const targetGain =
        entryPrice !== null && profitTarget !== null && entryPrice !== 0
            ? ((profitTarget - entryPrice) / entryPrice) * 100
            : null;

    return (
        <div className="border-t border-border pt-3">
            <h5 className="text-xs font-semibold text-text mb-2">Trade Levels</h5>
            <div className="grid grid-cols-3 gap-3 text-xs">
                {hasEntry && (
                    <div>
                        <p className="text-text-muted">Entry</p>
                        <p className="font-semibold text-green-600">
                            ${entryPrice!.toFixed(2)}
                        </p>
                    </div>
                )}
                {hasStop && (
                    <div>
                        <p className="text-text-muted">Stop</p>
                        <p className="font-semibold text-red-600">
                            ${stopLoss!.toFixed(2)}
                        </p>
                    </div>
                )}
                {hasTarget && (
                    <div>
                        <p className="text-text-muted">Target</p>
                        <p className="font-semibold text-blue-600">
                            ${profitTarget!.toFixed(2)}
                        </p>
                        {targetGain !== null && (
                            <p className="text-text-muted mt-0.5">
                                +{targetGain.toFixed(1)}%
                            </p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function PositionSizing({ item }: { item: WatchlistItem }) {
    const shares = item.position_size_shares;
    if (!isNumber(shares) || shares <= 0) {
        return null;
    }

    const entryPrice = isNumber(item.entry_price) ? Number(item.entry_price) : null;
    const investment = entryPrice !== null ? (shares * entryPrice).toFixed(2) : null;

    return (
        <div className="border-t border-border pt-3">
            <h5 className="text-xs font-semibold text-text mb-2">Position Sizing</h5>
            <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                    <p className="text-text-muted">Shares</p>
                    <p className="font-semibold text-text">{shares} shares</p>
                </div>
                {investment && (
                    <div>
                        <p className="text-text-muted">Investment</p>
                        <p className="font-semibold text-text">${investment}</p>
                    </div>
                )}
            </div>
        </div>
    );
}

function WhyThisWorks({ item }: { item: WatchlistItem }) {
    const copy = buildWhyThisWorksCopy(item);
    if (!copy) {
        return null;
    }

    return (
        <div className="border-t border-border pt-3 text-xs">
            <p className="font-semibold text-text mb-1 flex items-center gap-1">
                <span>💡</span>
                <span>WHY THIS WORKS:</span>
            </p>
            <p className="text-text-muted leading-relaxed">{copy}</p>
        </div>
    );
}

const STYLE_BADGES: Record<RecommendedStyle, { icon: string; color: string }> = {
    Index: { icon: "📈", color: "bg-blue-500/10 text-blue-600 border-blue-500/20" },
    Trend: { icon: "🔥", color: "bg-orange-500/10 text-orange-600 border-orange-500/20" },
    Value: { icon: "💎", color: "bg-purple-500/10 text-purple-600 border-purple-500/20" },
    Swing: { icon: "⚡", color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20" },
    Event: { icon: "📅", color: "bg-red-500/10 text-red-600 border-red-500/20" },
};

function getStyleDisplay(style?: RecommendedStyle | null) {
    if (!style) {
        return null;
    }
    return STYLE_BADGES[style];
}

function buildWhyThisWorksCopy(item: WatchlistItem): string | null {
    if (!item.signal_type) {
        return null;
    }

    const strength = isNumber(item.signal_strength) ? item.signal_strength : null;
    const styleDescriptor = describeStyle(item.recommended_style);
    const signal = item.signal_type as SignalType;

    if (signal === "BUY") {
        const momentum = strength !== null && strength >= 7 ? "strong" : "positive";
        const details = styleDescriptor ? ` ${styleDescriptor}` : " favorable conditions";
        const confirmation = strength !== null && strength >= 8
            ? " Multiple confirming indicators align for high-probability setup."
            : "";
        return `Technical setup shows ${momentum} momentum with${details}.${confirmation}`;
    }

    if (signal === "HOLD") {
        const valueNote =
            item.recommended_style === "Value"
                ? " Quality company but timing not optimal yet."
                : "";
        return `Mixed signals suggest waiting for clearer setup.${valueNote} Monitor for improvement in technical indicators before committing capital.`;
    }

    // AVOID
    const weakness = strength !== null && strength <= 3 ? "significant " : "";
    return `Technical indicators show ${weakness}weakness. Risk outweighs potential reward at current levels. Wait for stabilization and trend reversal confirmation.`;
}

function describeStyle(style?: WatchlistItem["recommended_style"] | null) {
    switch (style) {
        case "Trend":
            return "trend-following characteristics";
        case "Value":
            return "value opportunity";
        case "Swing":
            return "reversal potential";
        case "Event":
            return "catalyst-driven setup";
        case "Index":
            return "index-aligned momentum";
        default:
            return null;
    }
}

function isNumber(value: unknown): value is number {
    return typeof value === "number" && !Number.isNaN(value);
}

"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { fetchThesis, generateThesis, invalidateThesis } from "@/lib/api/thesis";
import type { Thesis, CoreReason, KeyCatalyst, Risk } from "@/lib/api/thesis";
import { formatTimestamp } from "./ExpandedRowUtils";

interface ThesisSectionProps {
    symbol: string;
    userTimezone: string;
}

/**
 * Thesis System UI Component
 *
 * Displays investment thesis with:
 * - Action recommendation (BUY/HOLD/SELL)
 * - Cross-validation score
 * - Core reasons with confidence bars
 * - Key catalysts with impact badges
 * - Risks with severity badges
 * - Value drivers
 * - Expected returns
 * - Version history
 */
export function ThesisSection({ symbol, userTimezone }: ThesisSectionProps) {
    const [showAdmin, setShowAdmin] = useState(false);
    const queryClient = useQueryClient();

    // Fetch thesis data
    const { data, isLoading, error } = useQuery({
        queryKey: ["thesis", symbol],
        queryFn: () => fetchThesis(symbol),
    });

    // Generate thesis mutation
    const generateMutation = useMutation({
        mutationFn: (forceRegenerate: boolean) =>
            generateThesis(symbol, { force_regenerate: forceRegenerate }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["thesis", symbol] });
        },
    });

    // Invalidate thesis mutation
    const invalidateMutation = useMutation({
        mutationFn: (reason: string) => invalidateThesis(symbol, reason),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["thesis", symbol] });
        },
    });

    if (isLoading) {
        return (
            <Card className="border-border">
                <CardContent className="p-6">
                    <div className="flex items-center justify-center">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (error) {
        return (
            <Card className="border-border border-red-500/20">
                <CardContent className="p-6">
                    <p className="text-sm text-red-600">
                        Error loading thesis: {error instanceof Error ? error.message : "Unknown error"}
                    </p>
                </CardContent>
            </Card>
        );
    }

    const thesis = data?.thesis;

    // No thesis exists
    if (!thesis) {
        return (
            <Card className="border-border">
                <CardHeader>
                    <CardTitle className="text-base">Investment Thesis</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <p className="text-sm text-text-muted">
                        No thesis generated for {symbol}
                    </p>
                    <Button
                        onClick={() => generateMutation.mutate(false)}
                        disabled={generateMutation.isPending}
                        size="sm"
                    >
                        {generateMutation.isPending ? "Generating..." : "Generate Thesis"}
                    </Button>
                </CardContent>
            </Card>
        );
    }

    return (
        <TooltipProvider delayDuration={200}>
            <Card className="border-border">
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">Investment Thesis</CardTitle>
                        <div className="flex items-center gap-2">
                            <ActionBadge action={thesis.action} />
                            {thesis.cross_validation_score !== null && (
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Badge variant="outline" className="cursor-help">
                                            Cross-Val: {(thesis.cross_validation_score * 100).toFixed(0)}%
                                        </Badge>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        <p className="text-xs">
                                            AI cross-validation confidence score
                                        </p>
                                    </TooltipContent>
                                </Tooltip>
                            )}
                            <StatusBadge status={thesis.status} />
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Core Reasons */}
                    <CoreReasonsSection reasons={thesis.core_reasons} />

                    {/* Key Catalysts */}
                    {thesis.key_catalysts.length > 0 && (
                        <KeyCatalystsSection
                            catalysts={thesis.key_catalysts}
                            userTimezone={userTimezone}
                        />
                    )}

                    {/* Risks */}
                    {thesis.risks.length > 0 && (
                        <RisksSection risks={thesis.risks} />
                    )}

                    {/* Value Drivers */}
                    {thesis.value_drivers && (
                        <ValueDriversSection drivers={thesis.value_drivers} />
                    )}

                    {/* Expected Returns */}
                    {(thesis.expected_return_pct !== null ||
                        thesis.expected_timeframe_days !== null) && (
                        <ExpectedReturnsSection thesis={thesis} />
                    )}

                    {/* Claude Validation */}
                    {thesis.claude_validation && (
                        <ClaudeValidationSection validation={thesis.claude_validation} />
                    )}

                    {/* Version History */}
                    {data.versions && data.versions.length > 1 && (
                        <VersionHistorySection
                            versions={data.versions}
                            userTimezone={userTimezone}
                        />
                    )}

                    {/* Action Buttons */}
                    <div className="border-t border-border pt-3 flex items-center gap-2">
                        <Button
                            onClick={() => generateMutation.mutate(true)}
                            disabled={generateMutation.isPending}
                            size="sm"
                            variant="outline"
                        >
                            {generateMutation.isPending ? "Regenerating..." : "Regenerate"}
                        </Button>
                        <Button
                            onClick={() => setShowAdmin(!showAdmin)}
                            size="sm"
                            variant="ghost"
                        >
                            {showAdmin ? "Hide Admin" : "Admin"}
                        </Button>
                        {showAdmin && (
                            <Button
                                onClick={() => invalidateMutation.mutate("Manual invalidation by user")}
                                disabled={invalidateMutation.isPending}
                                size="sm"
                                variant="destructive"
                            >
                                {invalidateMutation.isPending ? "Invalidating..." : "Invalidate"}
                            </Button>
                        )}
                        <div className="ml-auto text-xs text-text-muted">
                            v{thesis.version} • Updated {formatTimestamp(thesis.updated_at, userTimezone)}
                        </div>
                    </div>
                </CardContent>
            </Card>
        </TooltipProvider>
    );
}

// Action Badge Component
function ActionBadge({ action }: { action: "BUY" | "HOLD" | "SELL" }) {
    const config = {
        BUY: { color: "bg-green-500/10 text-green-600 border-green-500/20", icon: "📈" },
        HOLD: { color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20", icon: "⏸️" },
        SELL: { color: "bg-red-500/10 text-red-600 border-red-500/20", icon: "📉" },
    };

    const { color, icon } = config[action];

    return (
        <Badge className={`${color} font-semibold`}>
            <span className="mr-1">{icon}</span>
            {action}
        </Badge>
    );
}

// Status Badge Component
function StatusBadge({ status }: { status: "active" | "invalidated" | "flagged_for_review" }) {
    const config = {
        active: { color: "bg-blue-500/10 text-blue-600 border-blue-500/20", label: "Active" },
        invalidated: { color: "bg-gray-500/10 text-gray-600 border-gray-500/20", label: "Invalidated" },
        flagged_for_review: { color: "bg-orange-500/10 text-orange-600 border-orange-500/20", label: "Flagged" },
    };

    const { color, label } = config[status];

    return (
        <Badge variant="outline" className={color}>
            {label}
        </Badge>
    );
}

// Core Reasons Section
function CoreReasonsSection({ reasons }: { reasons: CoreReason[] }) {
    if (reasons.length === 0) return null;

    return (
        <div className="space-y-2">
            <h5 className="text-xs font-semibold text-text">Core Reasons</h5>
            <div className="space-y-2">
                {reasons.map((reason, idx) => (
                    <div key={idx} className="space-y-1">
                        <div className="flex items-start justify-between gap-2">
                            <p className="text-sm text-text flex-1">{reason.reason}</p>
                            <span className="text-xs font-semibold text-text-muted min-w-[40px] text-right">
                                {(reason.confidence * 100).toFixed(0)}%
                            </span>
                        </div>
                        <div className="h-1.5 bg-surface-muted rounded-full overflow-hidden">
                            <div
                                className={`h-full ${getConfidenceColor(reason.confidence)} transition-all`}
                                style={{ width: `${reason.confidence * 100}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Key Catalysts Section
function KeyCatalystsSection({
    catalysts,
    userTimezone,
}: {
    catalysts: KeyCatalyst[];
    userTimezone: string;
}) {
    return (
        <div className="border-t border-border pt-3 space-y-2">
            <h5 className="text-xs font-semibold text-text">Key Catalysts</h5>
            <div className="space-y-2">
                {catalysts.map((catalyst, idx) => (
                    <div key={idx} className="flex items-start gap-2">
                        <ImpactBadge impact={catalyst.impact} />
                        <div className="flex-1">
                            <p className="text-sm text-text">{catalyst.catalyst}</p>
                            {catalyst.expected_date && (
                                <p className="text-xs text-text-muted mt-0.5">
                                    Expected: {formatTimestamp(catalyst.expected_date, userTimezone)}
                                </p>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Impact Badge Component
function ImpactBadge({ impact }: { impact: "positive" | "negative" | "neutral" }) {
    const config = {
        positive: { color: "bg-green-500/10 text-green-600 border-green-500/20", icon: "+" },
        negative: { color: "bg-red-500/10 text-red-600 border-red-500/20", icon: "-" },
        neutral: { color: "bg-gray-500/10 text-gray-600 border-gray-500/20", icon: "~" },
    };

    const { color, icon } = config[impact];

    return (
        <Badge variant="outline" className={`${color} text-xs px-1.5 py-0 h-5`}>
            {icon}
        </Badge>
    );
}

// Risks Section
function RisksSection({ risks }: { risks: Risk[] }) {
    return (
        <div className="border-t border-border pt-3 space-y-2">
            <h5 className="text-xs font-semibold text-text">Risks</h5>
            <div className="space-y-2">
                {risks.map((risk, idx) => (
                    <div key={idx} className="space-y-1">
                        <div className="flex items-start gap-2">
                            <SeverityBadge severity={risk.severity} />
                            <div className="flex-1">
                                <p className="text-sm text-text">{risk.risk}</p>
                                {risk.mitigation && (
                                    <p className="text-xs text-text-muted mt-1">
                                        <span className="font-medium">Mitigation:</span> {risk.mitigation}
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Severity Badge Component
function SeverityBadge({ severity }: { severity: "high" | "medium" | "low" }) {
    const config = {
        high: { color: "bg-red-500/10 text-red-600 border-red-500/20", label: "High" },
        medium: { color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20", label: "Med" },
        low: { color: "bg-blue-500/10 text-blue-600 border-blue-500/20", label: "Low" },
    };

    const { color, label } = config[severity];

    return (
        <Badge variant="outline" className={`${color} text-xs px-1.5 py-0 h-5`}>
            {label}
        </Badge>
    );
}

// Value Drivers Section
function ValueDriversSection({ drivers }: { drivers: NonNullable<Thesis["value_drivers"]> }) {
    const items = [
        { label: "Market Size", value: drivers.market_size },
        { label: "Company Position", value: drivers.company_position },
        { label: "Upside Potential", value: drivers.upside_potential },
        { label: "Competitive Moat", value: drivers.competitive_moat },
    ].filter((item) => item.value !== null);

    if (items.length === 0) return null;

    return (
        <div className="border-t border-border pt-3 space-y-2">
            <h5 className="text-xs font-semibold text-text">Value Drivers</h5>
            <div className="grid grid-cols-2 gap-2">
                {items.map((item, idx) => (
                    <div key={idx} className="bg-surface-muted/50 rounded px-2 py-1.5">
                        <p className="text-xs text-text-muted">{item.label}</p>
                        <p className="text-sm font-medium text-text">{item.value}</p>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Expected Returns Section
function ExpectedReturnsSection({ thesis }: { thesis: Thesis }) {
    return (
        <div className="border-t border-border pt-3">
            <h5 className="text-xs font-semibold text-text mb-2">Expected Returns</h5>
            <div className="grid grid-cols-2 gap-3">
                {thesis.expected_return_pct !== null && (
                    <div className="bg-surface-muted/50 rounded px-2 py-1.5">
                        <p className="text-xs text-text-muted">Return</p>
                        <p className="text-sm font-semibold text-text">
                            {thesis.expected_return_pct > 0 ? "+" : ""}
                            {thesis.expected_return_pct.toFixed(1)}%
                        </p>
                    </div>
                )}
                {thesis.expected_timeframe_days !== null && (
                    <div className="bg-surface-muted/50 rounded px-2 py-1.5">
                        <p className="text-xs text-text-muted">Timeframe</p>
                        <p className="text-sm font-semibold text-text">
                            {thesis.expected_timeframe_days} days
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}

// Claude Validation Section
function ClaudeValidationSection({
    validation,
}: {
    validation: NonNullable<Thesis["claude_validation"]>;
}) {
    return (
        <div className="border-t border-border pt-3 space-y-2">
            <div className="flex items-center justify-between">
                <h5 className="text-xs font-semibold text-text">AI Validation</h5>
                <div className="flex items-center gap-2">
                    <Badge
                        variant="outline"
                        className={
                            validation.approved
                                ? "bg-green-500/10 text-green-600 border-green-500/20"
                                : "bg-red-500/10 text-red-600 border-red-500/20"
                        }
                    >
                        {validation.approved ? "Approved" : "Not Approved"}
                    </Badge>
                    <span className="text-xs text-text-muted">
                        {(validation.confidence * 100).toFixed(0)}% confidence
                    </span>
                </div>
            </div>
            <p className="text-sm text-text-muted">{validation.review_summary}</p>
            {validation.issues.length > 0 && (
                <div className="space-y-1">
                    <p className="text-xs font-medium text-text">Issues:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                        {validation.issues.map((issue, idx) => (
                            <li key={idx} className="text-xs text-text-muted">
                                {issue}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

// Version History Section
function VersionHistorySection({
    versions,
    userTimezone,
}: {
    versions: Array<{ version: number; status: string; action: string; created_at: string }>;
    userTimezone: string;
}) {
    return (
        <div className="border-t border-border pt-3">
            <Accordion type="single" collapsible>
                <AccordionItem value="history" className="border-0">
                    <AccordionTrigger className="hover:no-underline py-2 text-xs font-semibold">
                        Version History ({versions.length})
                    </AccordionTrigger>
                    <AccordionContent>
                        <div className="space-y-2 pt-2">
                            {versions.map((version) => (
                                <div
                                    key={version.version}
                                    className="flex items-center justify-between text-xs border-b border-border pb-2 last:border-0"
                                >
                                    <div className="flex items-center gap-2">
                                        <Badge variant="outline" className="text-xs">
                                            v{version.version}
                                        </Badge>
                                        <span className="text-text-muted">{version.action}</span>
                                        <Badge variant="outline" className="text-xs">
                                            {version.status}
                                        </Badge>
                                    </div>
                                    <span className="text-text-muted">
                                        {formatTimestamp(version.created_at, userTimezone)}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </AccordionContent>
                </AccordionItem>
            </Accordion>
        </div>
    );
}

// Utility Functions
function getConfidenceColor(confidence: number): string {
    if (confidence >= 0.8) return "bg-green-500";
    if (confidence >= 0.6) return "bg-blue-500";
    if (confidence >= 0.4) return "bg-yellow-500";
    return "bg-red-500";
}

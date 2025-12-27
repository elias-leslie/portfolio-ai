"use client";

import { useState } from "react";
import {
    Database,
    CheckCircle2,
    AlertCircle,
    XCircle,
    ChevronDown,
    ChevronRight,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { DayBarFreshnessInfo } from "@/lib/api/status";

interface DataFreshnessCardProps {
    freshness: DayBarFreshnessInfo[];
}

export function DataFreshnessCard({ freshness }: DataFreshnessCardProps) {
    const [isOpen, setIsOpen] = useState(true);

    if (!freshness || freshness.length === 0) {
        return (
            <Card className="border-border">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        <span>Day Bars Data Freshness</span>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-muted-foreground">
                        No dayBars data available. Price data may not have been ingested yet.
                    </p>
                </CardContent>
            </Card>
        );
    }

    // Categorize by freshness
    const fresh = freshness.filter((f) => (f.ageDays ?? 999) <= 1);
    const stale = freshness.filter((f) => (f.ageDays ?? 999) > 1 && (f.ageDays ?? 999) <= 7);
    const veryStale = freshness.filter((f) => (f.ageDays ?? 999) > 7);

    const getStatusIcon = (ageDays?: number) => {
        if (ageDays === undefined || ageDays === null) {
            return <XCircle className="h-4 w-4 text-text-muted" />;
        }
        if (ageDays <= 1) {
            return <CheckCircle2 className="h-4 w-4 text-status-success" />;
        }
        if (ageDays <= 7) {
            return <AlertCircle className="h-4 w-4 text-status-warning" />;
        }
        return <XCircle className="h-4 w-4 text-status-error" />;
    };

    const getStatusBadge = (ageDays?: number) => {
        if (ageDays === undefined || ageDays === null) {
            return <Badge variant="outline">No Data</Badge>;
        }
        if (ageDays <= 1) {
            return <Badge className="bg-status-success text-white">Fresh</Badge>;
        }
        if (ageDays <= 7) {
            return <Badge className="bg-status-warning text-white">Stale</Badge>;
        }
        return <Badge variant="destructive">Very Stale</Badge>;
    };

    const formatDate = (dateStr?: string) => {
        if (!dateStr) return "Never";
        try {
            return new Date(dateStr).toLocaleDateString();
        } catch {
            return "Invalid date";
        }
    };

    const renderSymbolRow = (item: DayBarFreshnessInfo) => (
        <div
            key={item.symbol}
            className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
        >
            <div className="flex items-center gap-3 flex-1">
                {getStatusIcon(item.ageDays)}
                <div className="flex-1">
                    <div className="font-medium font-mono">{item.symbol}</div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        <div>Last updated: {formatDate(item.lastUpdated)}</div>
                        {item.ageDays !== undefined && item.ageDays !== null && (
                            <div>
                                {item.ageDays === 0
                                    ? "Today"
                                    : item.ageDays === 1
                                      ? "1 day old"
                                      : `${item.ageDays} days old`}
                            </div>
                        )}
                    </div>
                </div>
            </div>
            <div>{getStatusBadge(item.ageDays)}</div>
        </div>
    );

    return (
        <Card className="border-border">
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        <span>Day Bars Data Freshness</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge className="bg-status-success text-white">{fresh.length} Fresh</Badge>
                        {stale.length > 0 && (
                            <Badge className="bg-status-warning text-white">{stale.length} Stale</Badge>
                        )}
                        {veryStale.length > 0 && (
                            <Badge variant="destructive">{veryStale.length} Very Stale</Badge>
                        )}
                    </div>
                </CardTitle>
            </CardHeader>
            <CardContent>
                <Collapsible open={isOpen} onOpenChange={setIsOpen}>
                    <CollapsibleTrigger asChild>
                        <Button variant="outline" className="w-full justify-between mb-3">
                            <div className="flex items-center gap-2">
                                {isOpen ? (
                                    <ChevronDown className="h-4 w-4" />
                                ) : (
                                    <ChevronRight className="h-4 w-4" />
                                )}
                                <span className="font-semibold">
                                    All Symbols ({freshness.length})
                                </span>
                            </div>
                        </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <div className="space-y-3">
                            {/* Very stale first */}
                            {veryStale.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-status-error">
                                        Very Stale (&gt;7 days)
                                    </div>
                                    {veryStale
                                        .sort((a, b) => a.symbol.localeCompare(b.symbol))
                                        .map(renderSymbolRow)}
                                </>
                            )}

                            {/* Stale second */}
                            {stale.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-status-warning mt-4">
                                        Stale (1-7 days)
                                    </div>
                                    {stale
                                        .sort((a, b) => a.symbol.localeCompare(b.symbol))
                                        .map(renderSymbolRow)}
                                </>
                            )}

                            {/* Fresh last */}
                            {fresh.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-status-success mt-4">
                                        Fresh (≤1 day)
                                    </div>
                                    {fresh
                                        .sort((a, b) => a.symbol.localeCompare(b.symbol))
                                        .map(renderSymbolRow)}
                                </>
                            )}
                        </div>
                    </CollapsibleContent>
                </Collapsible>

                <div className="mt-4 p-3 bg-muted/50 rounded-lg text-xs text-muted-foreground">
                    <p className="font-medium mb-1">Note:</p>
                    <p>
                        Data freshness indicates how recent the last dayBars entry is for each symbol.
                        Fresh data (&lt;1 day) is normal. Stale data may indicate ingestion issues or
                        market holidays.
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}

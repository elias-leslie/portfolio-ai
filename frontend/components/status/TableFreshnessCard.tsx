"use client";

import { useState, useEffect } from "react";
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
import { fetchTableFreshness, TableFreshnessResponse, TableFreshnessStatus } from "@/lib/api/status";

export function TableFreshnessCard() {
    const [data, setData] = useState<TableFreshnessResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isOpen, setIsOpen] = useState(false); // Default to collapsed

    useEffect(() => {
        const loadFreshness = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const response = await fetchTableFreshness();
                setData(response);
            } catch (err) {
                console.error("Failed to fetch table freshness:", err);
                setError("Failed to load table freshness data");
            } finally {
                setIsLoading(false);
            }
        };

        loadFreshness();
        // Refresh every 60 seconds
        const interval = setInterval(loadFreshness, 60000);

        return () => clearInterval(interval);
    }, []);

    if (isLoading && !data) {
        return (
            <Card className="border-border">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        <span>Data Freshness</span>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-muted-foreground">Loading table freshness...</p>
                </CardContent>
            </Card>
        );
    }

    if (error || !data) {
        return (
            <Card className="border-border">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        <span>Data Freshness</span>
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <p className="text-sm text-destructive">{error || "No data available"}</p>
                </CardContent>
            </Card>
        );
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case "fresh":
                return <CheckCircle2 className="h-4 w-4 text-green-500" />;
            case "stale":
                return <AlertCircle className="h-4 w-4 text-yellow-500" />;
            case "critical":
                return <XCircle className="h-4 w-4 text-red-500" />;
            default:
                return <XCircle className="h-4 w-4 text-gray-500" />;
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "fresh":
                return <Badge className="bg-green-500 text-white">Fresh</Badge>;
            case "stale":
                return <Badge className="bg-yellow-500 text-white">Stale</Badge>;
            case "critical":
                return <Badge variant="destructive">Critical</Badge>;
            case "error":
                return <Badge variant="outline">Error</Badge>;
            default:
                return <Badge variant="outline">Unknown</Badge>;
        }
    };

    const formatTimestamp = (timestamp: string | null) => {
        if (!timestamp) return "Never";
        try {
            const date = new Date(timestamp);
            return date.toLocaleString();
        } catch {
            return "Invalid date";
        }
    };

    const formatAge = (ageHours: number | null) => {
        if (ageHours === null) return "Unknown";
        if (ageHours < 1) return `${Math.round(ageHours * 60)}m ago`;
        if (ageHours < 24) return `${Math.round(ageHours)}h ago`;
        const days = Math.round(ageHours / 24);
        return `${days}d ago`;
    };

    const formatTableName = (tableName: string) => {
        // Convert snake_case to Title Case
        return tableName
            .split("_")
            .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
            .join(" ");
    };

    const renderTableRow = (table: TableFreshnessStatus) => (
        <div
            key={table.table_name}
            className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-colors"
            title={`${table.description}\nExpected refresh: every ${table.expected_refresh_hours}h\nLast updated: ${formatTimestamp(table.last_updated)}`}
        >
            <div className="flex items-center gap-3 flex-1">
                {getStatusIcon(table.status)}
                <div className="flex-1">
                    <div className="font-medium">{formatTableName(table.table_name)}</div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        <div>{formatAge(table.age_hours)}</div>
                        <div className="text-muted-foreground/70">
                            (refreshes every {table.expected_refresh_hours}h)
                        </div>
                        {table.row_count !== null && table.row_count > 0 && (
                            <div>{table.row_count.toLocaleString()} rows</div>
                        )}
                    </div>
                </div>
            </div>
            <div>{getStatusBadge(table.status)}</div>
        </div>
    );

    // Group tables by status
    const freshTables = data.tables.filter((t) => t.status === "fresh");
    const staleTables = data.tables.filter((t) => t.status === "stale");
    const criticalTables = data.tables.filter((t) => t.status === "critical");
    const errorTables = data.tables.filter((t) => t.status === "error" || t.status === "unknown");

    // Determine overall status color
    const getOverallColor = () => {
        if (criticalTables.length > 0) return "bg-red-500";
        if (staleTables.length > 0) return "bg-yellow-500";
        return "bg-green-500";
    };

    return (
        <Card className="border-border">
            <CardHeader>
                <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        <span>Data Freshness</span>
                    </div>
                    <div className="flex items-center gap-2">
                        {data.fresh_count > 0 && (
                            <Badge className="bg-green-500 text-white">{data.fresh_count} Fresh</Badge>
                        )}
                        {data.stale_count > 0 && (
                            <Badge className="bg-yellow-500 text-white">{data.stale_count} Stale</Badge>
                        )}
                        {data.critical_count > 0 && (
                            <Badge variant="destructive">{data.critical_count} Critical</Badge>
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
                                    {isOpen ? "Hide" : "Show"} All Tables ({data.tables.length})
                                </span>
                            </div>
                            <Badge className={`${getOverallColor()} text-white`}>
                                {criticalTables.length > 0
                                    ? "Action Required"
                                    : staleTables.length > 0
                                      ? "Attention Needed"
                                      : "All Fresh"}
                            </Badge>
                        </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                        <div className="space-y-3">
                            {/* Critical tables first */}
                            {criticalTables.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-red-600">
                                        Critical (&gt;48h old)
                                    </div>
                                    {criticalTables
                                        .sort((a, b) => a.table_name.localeCompare(b.table_name))
                                        .map(renderTableRow)}
                                </>
                            )}

                            {/* Stale tables second */}
                            {staleTables.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-yellow-600 mt-4">
                                        Stale (24-48h old)
                                    </div>
                                    {staleTables
                                        .sort((a, b) => a.table_name.localeCompare(b.table_name))
                                        .map(renderTableRow)}
                                </>
                            )}

                            {/* Fresh tables third */}
                            {freshTables.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-green-600 mt-4">
                                        Fresh (&lt;24h old)
                                    </div>
                                    {freshTables
                                        .sort((a, b) => a.table_name.localeCompare(b.table_name))
                                        .map(renderTableRow)}
                                </>
                            )}

                            {/* Error tables last */}
                            {errorTables.length > 0 && (
                                <>
                                    <div className="text-sm font-semibold text-gray-600 mt-4">
                                        No Data / Error
                                    </div>
                                    {errorTables
                                        .sort((a, b) => a.table_name.localeCompare(b.table_name))
                                        .map(renderTableRow)}
                                </>
                            )}
                        </div>
                    </CollapsibleContent>
                </Collapsible>

                <div className="mt-4 p-3 bg-muted/50 rounded-lg text-xs text-muted-foreground">
                    <p className="font-medium mb-1">Data Freshness Status:</p>
                    <ul className="list-disc list-inside space-y-1">
                        <li>
                            <span className="text-green-600">Fresh:</span> Updated within expected refresh interval
                        </li>
                        <li>
                            <span className="text-yellow-600">Stale:</span> Overdue but within 2x expected interval
                        </li>
                        <li>
                            <span className="text-red-600">Critical:</span> Over 2x expected refresh interval
                        </li>
                    </ul>
                    <p className="mt-2 text-muted-foreground/70">
                        Each table has its own refresh schedule (shown in parentheses). Hover over a table for details.
                    </p>
                </div>
            </CardContent>
        </Card>
    );
}

"use client";

import React, { useState, useMemo } from "react";
import {
    FileText,
    RefreshCw,
    Filter,
    Copy,
    Check,
    ArrowUpDown,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import useSWR from "swr";

interface UnifiedLogEntry {
    timestamp: string;
    service: string;
    level: "ERROR" | "WARN" | "INFO" | "DEBUG" | "UNKNOWN";
    message: string;
}

interface UnifiedLogsResponse {
    logs: UnifiedLogEntry[];
    total_entries: number;
    timestamp: string;
}

const SERVICE_DISPLAY_NAMES: Record<string, string> = {
    backend: "Backend",
    celery_worker: "Celery Worker",
    celery_beat: "Celery Beat",
    frontend: "Frontend",
    redis: "Redis",
    postgresql: "PostgreSQL",
};

const fetcher = (url: string) => fetch(url).then((res) => res.json());

/**
 * Get CSS color class for log level.
 */
function getLevelColor(level: string): string {
    switch (level) {
        case "ERROR":
            return "text-red-400";
        case "WARN":
            return "text-yellow-400";
        case "INFO":
            return "text-blue-400";
        case "DEBUG":
            return "text-gray-400";
        default:
            return "text-gray-300";
    }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp: string): string {
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    } catch {
        return timestamp;
    }
}

interface LogsCardProps {
    autoRefresh?: boolean;
}

export function LogsCard({ autoRefresh = false }: LogsCardProps) {
    const [levelFilter, setLevelFilter] = useState<string | undefined>(undefined);
    const [serviceFilter, setServiceFilter] = useState<string | undefined>(undefined);
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
    const [copied, setCopied] = useState(false);

    // Build API URL with filters
    const apiUrl = useMemo(() => {
        const params = new URLSearchParams({
            lines: "500",
            since: "5 minutes ago",
        });
        if (levelFilter && levelFilter !== "ALL") params.append("level", levelFilter);
        if (serviceFilter && serviceFilter !== "ALL") params.append("service", serviceFilter);
        // Use backend URL (same server, port 8000)
        const backendUrl = typeof window !== 'undefined'
            ? `http://${window.location.hostname}:8000`
            : 'http://localhost:8000';
        return `${backendUrl}/api/status/unified-logs?${params}`;
    }, [levelFilter, serviceFilter]);

    // Fetch unified logs from API
    const { data, error, isLoading } = useSWR<UnifiedLogsResponse>(
        apiUrl,
        fetcher,
        {
            refreshInterval: autoRefresh ? 5000 : 0,
            revalidateOnFocus: false,
        }
    );

    // Sort logs by timestamp
    const sortedLogs = useMemo(() => {
        if (!data?.logs) return [];
        const logs = [...data.logs];
        logs.sort((a, b) => {
            const timeA = new Date(a.timestamp).getTime();
            const timeB = new Date(b.timestamp).getTime();
            return sortOrder === "asc" ? timeA - timeB : timeB - timeA;
        });
        return logs;
    }, [data?.logs, sortOrder]);

    // Get log level counts
    const logCounts = useMemo(() => {
        const counts: Record<string, number> = {
            ERROR: 0,
            WARN: 0,
            INFO: 0,
            DEBUG: 0,
            UNKNOWN: 0,
        };
        data?.logs.forEach((log) => {
            counts[log.level] = (counts[log.level] || 0) + 1;
        });
        return counts;
    }, [data?.logs]);

    // Copy logs to clipboard
    const handleCopy = async () => {
        const text = sortedLogs
            .map((log) => `[${formatTimestamp(log.timestamp)}] [${SERVICE_DISPLAY_NAMES[log.service] || log.service}] [${log.level}] ${log.message}`)
            .join("\n");
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const toggleSortOrder = () => {
        setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    };

    return (
        <Card className="border-border">
            <CardHeader>
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <FileText className="h-5 w-5" />
                            <span>System Logs</span>
                        </CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">
                            Unified chronological view (last 5 minutes)
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline">
                            {sortedLogs.length} logs
                        </Badge>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={toggleSortOrder}
                            title={sortOrder === "desc" ? "Newest first" : "Oldest first"}
                        >
                            <ArrowUpDown className="mr-2 h-4 w-4" />
                            {sortOrder === "desc" ? "Newest" : "Oldest"}
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleCopy}>
                            {copied ? (
                                <>
                                    <Check className="mr-2 h-4 w-4" />
                                    Copied
                                </>
                            ) : (
                                <>
                                    <Copy className="mr-2 h-4 w-4" />
                                    Copy
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                {/* Filters */}
                <div className="flex items-center gap-4 mb-4">
                    <div className="flex items-center gap-2">
                        <Filter className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm font-medium">Filters:</span>
                    </div>
                    <Select value={serviceFilter || "ALL"} onValueChange={(val) => setServiceFilter(val === "ALL" ? undefined : val)}>
                        <SelectTrigger className="w-[200px]">
                            <SelectValue placeholder="All Services" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="ALL">All Services</SelectItem>
                            {Object.entries(SERVICE_DISPLAY_NAMES).map(([key, name]) => (
                                <SelectItem key={key} value={key}>
                                    {name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Select value={levelFilter || "ALL"} onValueChange={(val) => setLevelFilter(val === "ALL" ? undefined : val)}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Levels" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="ALL">
                                All Levels ({data?.total_entries || 0})
                            </SelectItem>
                            <SelectItem value="ERROR">
                                Error ({logCounts.ERROR})
                            </SelectItem>
                            <SelectItem value="WARN">
                                Warning ({logCounts.WARN})
                            </SelectItem>
                            <SelectItem value="INFO">Info ({logCounts.INFO})</SelectItem>
                            <SelectItem value="DEBUG">
                                Debug ({logCounts.DEBUG})
                            </SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                {/* Error state */}
                {error && (
                    <Alert variant="destructive" className="mb-4">
                        <AlertDescription>
                            Failed to load unified logs. Check service status.
                        </AlertDescription>
                    </Alert>
                )}

                {/* Loading state */}
                {isLoading && (
                    <div className="flex items-center justify-center p-8">
                        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading logs...</span>
                    </div>
                )}

                {/* Log stream */}
                {!isLoading && (
                    <ScrollArea className="h-[600px] w-full rounded-md border bg-gray-950 p-4">
                        {sortedLogs.length === 0 ? (
                            <div className="text-sm text-muted-foreground text-center py-8">
                                {levelFilter || serviceFilter
                                    ? "No logs match the selected filters"
                                    : "No logs available"}
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {sortedLogs.map((log, idx) => (
                                    <div
                                        key={idx}
                                        className={`font-mono text-xs ${getLevelColor(log.level)}`}
                                    >
                                        <div>
                                            <span className="text-gray-400">[{formatTimestamp(log.timestamp)}]</span>{" "}
                                            <span className="text-gray-500">[{SERVICE_DISPLAY_NAMES[log.service] || log.service}]</span>{" "}
                                            <span className={getLevelColor(log.level)}>[{log.level}]</span>
                                        </div>
                                        <pre className="whitespace-pre-wrap break-words ml-4 mt-0.5">{log.message}</pre>
                                    </div>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                )}
            </CardContent>
        </Card>
    );
}

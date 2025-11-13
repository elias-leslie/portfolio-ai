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
import { toast } from "sonner";

interface UnifiedLogEntry {
    timestamp: string;
    service: string;
    level: "CRITICAL" | "ERROR" | "WARN" | "INFO" | "DEBUG" | "UNKNOWN";
    message: string;
}

interface UnifiedLogsResponse {
    logs: UnifiedLogEntry[];
    total_entries: number;
    level_counts: Record<string, number>;
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
        case "CRITICAL":
            return "text-red-600 font-bold";
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
    const [changingLogLevel, setChangingLogLevel] = useState(false);
    const [restartRequired, setRestartRequired] = useState(false);
    const [restarting, setRestarting] = useState(false);
    const [refreshInterval, setRefreshInterval] = useState<number>(30000); // Default 30 seconds
    const [timeRange, setTimeRange] = useState<string>("5 minutes ago"); // Default 5 minutes

    // Build API URL with filters
    const apiUrl = useMemo(() => {
        const params = new URLSearchParams({
            lines: "500",
            since: timeRange,
        });
        if (levelFilter && levelFilter !== "ALL") params.append("level", levelFilter);
        if (serviceFilter && serviceFilter !== "ALL") params.append("service", serviceFilter);
        // Use backend URL (same server, port 8000)
        const backendUrl = typeof window !== 'undefined'
            ? `http://${window.location.hostname}:8000`
            : 'http://localhost:8000';
        return `${backendUrl}/api/status/unified-logs?${params}`;
    }, [levelFilter, serviceFilter, timeRange]);

    // Fetch unified logs from API
    const { data, error, isLoading } = useSWR<UnifiedLogsResponse>(
        apiUrl,
        fetcher,
        {
            refreshInterval: refreshInterval,
            revalidateOnFocus: false,
        }
    );

    // Fetch current log level configuration
    const backendUrl = typeof window !== 'undefined'
        ? `http://${window.location.hostname}:8000`
        : 'http://localhost:8000';
    const { data: logLevelConfig, mutate: mutateLogLevel } = useSWR(
        `${backendUrl}/api/status/log-level`,
        fetcher,
        { refreshInterval: 0 }
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

    // Get log level counts from API response (counts are from unfiltered data)
    const logCounts = useMemo(() => {
        return data?.level_counts || {
            CRITICAL: 0,
            ERROR: 0,
            WARN: 0,
            INFO: 0,
            DEBUG: 0,
            UNKNOWN: 0,
        };
    }, [data?.level_counts]);

    // Calculate total unfiltered log count
    const totalUnfilteredCount = useMemo(() => {
        return (logCounts.CRITICAL || 0) +
               (logCounts.ERROR || 0) +
               (logCounts.WARN || 0) +
               (logCounts.INFO || 0) +
               (logCounts.DEBUG || 0) +
               (logCounts.UNKNOWN || 0);
    }, [logCounts]);

    // Get log service counts
    const serviceCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        data?.logs.forEach((log) => {
            counts[log.service] = (counts[log.service] || 0) + 1;
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

    const handleLogLevelChange = async (newLevel: string) => {
        if (changingLogLevel) return;

        setChangingLogLevel(true);
        try {
            const response = await fetch(`${backendUrl}/api/status/log-level`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level: newLevel }),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to change log level');
            }

            const result = await response.json();

            // Refresh log level config
            await mutateLogLevel();

            // Show restart required
            setRestartRequired(true);

        } catch (error) {
            console.error('Failed to change log level:', error);
            toast.error(
                `Failed to change log level: ${
                    error instanceof Error ? error.message : "Unknown error"
                }`,
            );
        } finally {
            setChangingLogLevel(false);
        }
    };

    const handleRestartServices = async () => {
        if (restarting) return;

        setRestarting(true);
        try {
            const response = await fetch(`${backendUrl}/api/status/restart-services`, {
                method: 'POST',
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to restart services');
            }

            // Clear restart required flag
            setRestartRequired(false);

            // Refresh log level config
            await mutateLogLevel();

            toast.success("Services restarted successfully!");

        } catch (error) {
            console.error('Failed to restart services:', error);
            toast.error(
                `Failed to restart services: ${
                    error instanceof Error ? error.message : "Unknown error"
                }`,
            );
        } finally {
            setRestarting(false);
        }
    };

    return (
        <Card className="border-border">
            <CardHeader>
                <div className="flex items-center justify-between gap-2 flex-nowrap">
                    <CardTitle className="flex items-center gap-2 shrink-0">
                        <FileText className="h-5 w-5" />
                        <span className="whitespace-nowrap">Unified Logging</span>
                    </CardTitle>
                    <div className="flex items-center gap-2 flex-nowrap">
                        <Select value={serviceFilter || "ALL"} onValueChange={(val) => setServiceFilter(val === "ALL" ? undefined : val)}>
                            <SelectTrigger className="h-8 whitespace-nowrap">
                                <SelectValue placeholder="All Services" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="ALL">All Services ({totalUnfilteredCount})</SelectItem>
                                {Object.entries(SERVICE_DISPLAY_NAMES).map(([key, name]) => (
                                    <SelectItem key={key} value={key}>{name} ({serviceCounts[key] || 0})</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        <Select value={levelFilter || "ALL"} onValueChange={(val) => setLevelFilter(val === "ALL" ? undefined : val)}>
                            <SelectTrigger className="h-8 whitespace-nowrap">
                                <SelectValue placeholder="All Levels" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="ALL">All Levels ({totalUnfilteredCount})</SelectItem>
                                <SelectItem value="CRITICAL">Critical ({logCounts.CRITICAL || 0})</SelectItem>
                                <SelectItem value="ERROR">Error ({logCounts.ERROR || 0})</SelectItem>
                                <SelectItem value="WARN">Warning ({logCounts.WARN || 0})</SelectItem>
                                <SelectItem value="INFO">Info ({logCounts.INFO || 0})</SelectItem>
                                <SelectItem value="DEBUG">Debug ({logCounts.DEBUG || 0})</SelectItem>
                            </SelectContent>
                        </Select>
                        <Select value={timeRange} onValueChange={setTimeRange}>
                            <SelectTrigger className="h-8 whitespace-nowrap">
                                <SelectValue placeholder="Time Range" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1 minute ago">Last 1 min</SelectItem>
                                <SelectItem value="5 minutes ago">Last 5 min</SelectItem>
                                <SelectItem value="15 minutes ago">Last 15 min</SelectItem>
                                <SelectItem value="1 hour ago">Last 1 hour</SelectItem>
                                <SelectItem value="24 hours ago">Last 24 hours</SelectItem>
                            </SelectContent>
                        </Select>
                        <div className="w-px h-6 bg-border shrink-0" />
                        <Select
                            value={logLevelConfig?.current_level || "INFO"}
                            onValueChange={handleLogLevelChange}
                            disabled={changingLogLevel}
                        >
                            <SelectTrigger className="h-8 whitespace-nowrap">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="DEBUG">DEBUG</SelectItem>
                                <SelectItem value="INFO">INFO</SelectItem>
                                <SelectItem value="WARN">WARN</SelectItem>
                                <SelectItem value="ERROR">ERROR</SelectItem>
                                <SelectItem value="CRITICAL">CRITICAL</SelectItem>
                            </SelectContent>
                        </Select>
                        {changingLogLevel && <RefreshCw className="h-4 w-4 animate-spin shrink-0" />}
                        <Select
                            value={refreshInterval.toString()}
                            onValueChange={(val) => setRefreshInterval(parseInt(val))}
                        >
                            <SelectTrigger className="h-8 whitespace-nowrap">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="1000">1s</SelectItem>
                                <SelectItem value="5000">5s</SelectItem>
                                <SelectItem value="15000">15s</SelectItem>
                                <SelectItem value="30000">30s</SelectItem>
                                <SelectItem value="60000">60s</SelectItem>
                                <SelectItem value="0">Off</SelectItem>
                            </SelectContent>
                        </Select>
                        <div className="w-px h-6 bg-border shrink-0" />
                        <Badge variant="outline" className="shrink-0">{sortedLogs.length}</Badge>
                        <Button variant="outline" size="sm" onClick={toggleSortOrder} title={sortOrder === "desc" ? "Newest first" : "Oldest first"} className="shrink-0">
                            <ArrowUpDown className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="sm" onClick={handleCopy} className="shrink-0">
                            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>

                {restartRequired && !restarting && (
                    <Alert className="mb-4">
                        <AlertDescription>
                            <div className="flex items-center justify-between">
                                <span>Log level updated. Restart services to apply changes?</span>
                                <Button
                                    variant="default"
                                    size="sm"
                                    onClick={handleRestartServices}
                                >
                                    Restart Services
                                </Button>
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {restarting && (
                    <Alert className="mb-4">
                        <AlertDescription>
                            <div className="flex items-center gap-2">
                                <RefreshCw className="h-4 w-4 animate-spin" />
                                <span>Restarting services... This will take about 10 seconds.</span>
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

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

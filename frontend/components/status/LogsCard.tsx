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
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import {
    fetchUnifiedLogs,
    fetchLogLevelConfig,
    setLogLevel,
    restartAllServices,
    type UnifiedLogsResponse,
    type LogLevelConfig,
} from "@/lib/api/status";

const SERVICE_DISPLAY_NAMES: Record<string, string> = {
    backend: "Backend",
    celeryWorker: "Celery Worker",
    celeryBeat: "Celery Beat",
    frontend: "Frontend",
    redis: "Redis",
    postgresql: "PostgreSQL",
};

export function LogsCard() {
    const queryClient = useQueryClient();
    const [levelFilter, setLevelFilter] = useState<string | undefined>(undefined);
    const [serviceFilter, setServiceFilter] = useState<string | undefined>(undefined);
    const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
    const [copied, setCopied] = useState(false);
    const [restartRequired, setRestartRequired] = useState(false);
    const [refreshInterval, setRefreshInterval] = useState<number>(30000);
    const [timeRange, setTimeRange] = useState<string>("5 minutes ago");

    // Unified logs query
    const { data, error, isLoading } = useQuery<UnifiedLogsResponse>({
        queryKey: ["unified-logs", levelFilter, serviceFilter, timeRange],
        queryFn: () => fetchUnifiedLogs({
            lines: 500,
            since: timeRange,
            level: levelFilter && levelFilter !== "ALL" ? levelFilter : undefined,
            service: serviceFilter && serviceFilter !== "ALL" ? serviceFilter : undefined,
        }),
        refetchInterval: refreshInterval || false,
        refetchOnWindowFocus: false,
        staleTime: 0,
    });

    // Log level config query
    const { data: logLevelConfig } = useQuery<LogLevelConfig>({
        queryKey: ["log-level-config"],
        queryFn: fetchLogLevelConfig,
        refetchInterval: false,
        staleTime: 60000, // Cache for 1 minute
    });

    // Mutation for changing log level
    const logLevelMutation = useMutation({
        mutationFn: setLogLevel,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["log-level-config"] });
            setRestartRequired(true);
        },
        onError: (error) => {
            toast.error(
                `Failed to change log level: ${
                    error instanceof Error ? error.message : "Unknown error"
                }`,
            );
        },
    });

    // Mutation for restarting services
    const restartMutation = useMutation({
        mutationFn: restartAllServices,
        onSuccess: () => {
            setRestartRequired(false);
            queryClient.invalidateQueries({ queryKey: ["log-level-config"] });
            toast.success("Services restarted successfully!");
        },
        onError: (error) => {
            toast.error(
                `Failed to restart services: ${
                    error instanceof Error ? error.message : "Unknown error"
                }`,
            );
        },
    });

    // Extract logs for stable dependency - React Compiler optimization
    const logs = data?.logs;
    const sortedLogs = useMemo(() => {
        if (!logs) return [];
        // Use toSorted to avoid mutating and ensure stable reference
        return [...logs].toSorted((a, b) => {
            const timeA = new Date(a.timestamp).getTime();
            const timeB = new Date(b.timestamp).getTime();
            return sortOrder === "asc" ? timeA - timeB : timeB - timeA;
        });
    }, [logs, sortOrder]);

    const logCounts = useMemo(() => {
        return data?.levelCounts || {
            CRITICAL: 0,
            ERROR: 0,
            WARN: 0,
            INFO: 0,
            DEBUG: 0,
            UNKNOWN: 0,
        };
    }, [data?.levelCounts]);

    const totalUnfilteredCount = useMemo(() => {
        return (logCounts.CRITICAL || 0) +
               (logCounts.ERROR || 0) +
               (logCounts.WARN || 0) +
               (logCounts.INFO || 0) +
               (logCounts.DEBUG || 0) +
               (logCounts.UNKNOWN || 0);
    }, [logCounts]);

    const serviceCounts = useMemo(() => {
        const counts: Record<string, number> = {};
        data?.logs.forEach((log) => {
            counts[log.service] = (counts[log.service] || 0) + 1;
        });
        return counts;
    }, [data?.logs]);

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

    const handleLogLevelChange = (newLevel: string) => {
        if (logLevelMutation.isPending) return;
        logLevelMutation.mutate(newLevel);
    };

    const handleRestartServices = () => {
        if (restartMutation.isPending) return;
        restartMutation.mutate();
    };

    const summary = [
        `${sortedLogs.length} entries`,
        `Level ${logLevelConfig?.currentLevel ?? "INFO"}`,
        serviceFilter ? SERVICE_DISPLAY_NAMES[serviceFilter] : "All services",
    ]
        .filter(Boolean)
        .join(" • ");

    return (
        <ExpandableCard
            title={
                <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    <span>Unified Logging</span>
                </div>
            }
            description="Live log stream with filtering, log-level control, and restart tooling."
            summary={summary}
            defaultCollapsed
        >
            <div className="space-y-4">
                <TooltipProvider>
                    <div className="flex flex-wrap items-center gap-2">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="inline-block">
                                    <Select value={serviceFilter || "ALL"} onValueChange={(val) => setServiceFilter(val === "ALL" ? undefined : val)}>
                                        <SelectTrigger className="h-8 min-w-[150px]">
                                            <SelectValue placeholder="All Services" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="ALL">All Services ({totalUnfilteredCount})</SelectItem>
                                            {Object.entries(SERVICE_DISPLAY_NAMES).map(([key, name]) => (
                                                <SelectItem key={key} value={key}>{name} ({serviceCounts[key] || 0})</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Filter logs by specific service (e.g., Backend, Celery)</p>
                            </TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="inline-block">
                                    <Select value={levelFilter || "ALL"} onValueChange={(val) => setLevelFilter(val === "ALL" ? undefined : val)}>
                                        <SelectTrigger className="h-8 min-w-[130px]">
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
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Filter logs by severity level</p>
                            </TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="inline-block">
                                    <Select value={timeRange} onValueChange={setTimeRange}>
                                        <SelectTrigger className="h-8 min-w-[140px]">
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
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Select the time window for fetching logs</p>
                            </TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="inline-block">
                                    <Select
                                        value={logLevelConfig?.currentLevel || "INFO"}
                                        onValueChange={handleLogLevelChange}
                                        disabled={logLevelMutation.isPending}
                                    >
                                        <SelectTrigger className="h-8 min-w-[120px]">
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
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Change the global log level for all services</p>
                            </TooltipContent>
                        </Tooltip>

                        {logLevelMutation.isPending && <RefreshCw className="h-4 w-4 animate-spin shrink-0" />}

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="inline-block">
                                    <Select
                                        value={refreshInterval.toString()}
                                        onValueChange={(val) => setRefreshInterval(parseInt(val))}
                                    >
                                        <SelectTrigger className="h-8 min-w-[110px]">
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
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Set the auto-refresh interval</p>
                            </TooltipContent>
                        </Tooltip>

                        <Badge variant="outline" className="shrink-0">{sortedLogs.length}</Badge>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="outline" size="sm" onClick={toggleSortOrder} className="shrink-0">
                                    <ArrowUpDown className="h-4 w-4" />
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Toggle sort order ({sortOrder === "asc" ? "Oldest First" : "Newest First"})</p>
                            </TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button variant="outline" size="sm" onClick={handleCopy} className="shrink-0">
                                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>Copy visible logs to clipboard</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                </TooltipProvider>

                {restartRequired && !restartMutation.isPending && (
                    <Alert className="mb-0">
                        <AlertDescription>
                            <div className="flex items-center justify-between gap-2 flex-wrap">
                                <div className="flex items-center gap-2">
                                    <Filter className="h-4 w-4 text-warning" />
                                    <span>
                                        Log level changed. Restart services to apply the new level.
                                    </span>
                                </div>
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

                {restartMutation.isPending && (
                    <Alert className="mb-0">
                        <AlertDescription>
                            <div className="flex items-center gap-2">
                                <RefreshCw className="h-4 w-4 animate-spin" />
                                <span>Restarting services... This will take about 10 seconds.</span>
                            </div>
                        </AlertDescription>
                    </Alert>
                )}

                {error && (
                    <Alert variant="destructive" className="mb-0">
                        <AlertDescription>
                            Failed to load unified logs. Check service status.
                        </AlertDescription>
                    </Alert>
                )}

                {isLoading && (
                    <div className="flex items-center justify-center p-8">
                        <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                        <span className="ml-2 text-muted-foreground">Loading logs...</span>
                    </div>
                )}

                {!isLoading && (
                    <ScrollArea className="h-[600px] w-full rounded-md border bg-bg p-4">
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
                                            <span className="text-text-muted">[{formatTimestamp(log.timestamp)}]</span>{" "}
                                            <span className="text-text-muted/70">[{SERVICE_DISPLAY_NAMES[log.service] || log.service}]</span>{" "}
                                            <span className={getLevelColor(log.level)}>[{log.level}]</span>
                                        </div>
                                        <pre className="whitespace-pre-wrap break-words ml-4 mt-0.5">{log.message}</pre>
                                    </div>
                                ))}
                            </div>
                        )}
                    </ScrollArea>
                )}
            </div>
        </ExpandableCard>
    );
}

function getLevelColor(level: string): string {
    switch (level) {
        case "CRITICAL":
            return "text-loss font-bold";
        case "ERROR":
            return "text-loss";
        case "WARN":
            return "text-warning";
        case "INFO":
            return "text-accent";
        case "DEBUG":
            return "text-text-muted";
        default:
            return "text-text-muted";
    }
}

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

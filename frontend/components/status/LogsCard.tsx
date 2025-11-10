"use client";

import { useState, useMemo } from "react";
import {
    ChevronDown,
    ChevronRight,
    FileText,
    AlertCircle,
    AlertTriangle,
    Info,
    Bug,
    RefreshCw,
    Filter,
    ChevronUp,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { useServiceLogs } from "@/lib/hooks/useServiceLogs";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface ParsedLog {
    service: string;
    level: "ERROR" | "WARN" | "INFO" | "DEBUG" | "UNKNOWN";
    timestamp: string;
    message: string;
    fullLine: string;
}

const LOG_SERVICES = ["backend", "celery_worker", "celery_beat", "frontend", "redis"];

function parseLogLine(line: string, service: string): ParsedLog {
    // Try to extract log level
    let level: ParsedLog["level"] = "UNKNOWN";
    if (line.includes("ERROR") || line.includes("[error]")) {
        level = "ERROR";
    } else if (line.includes("WARN") || line.includes("[warn]")) {
        level = "WARN";
    } else if (line.includes("INFO") || line.includes("[info]")) {
        level = "INFO";
    } else if (line.includes("DEBUG") || line.includes("[debug]")) {
        level = "DEBUG";
    }

    // Try to extract timestamp (common formats)
    // Format 1: ISO8601 (2025-01-01T12:00:00Z or 2025-01-01 12:00:00)
    // Format 2: [2025-01-01 12:00:00]
    let timestamp = "";
    const isoMatch = line.match(/\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?/);
    if (isoMatch) {
        timestamp = isoMatch[0];
    } else {
        // Fallback: look for bracketed timestamp
        const bracketMatch = line.match(/\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]/);
        if (bracketMatch) {
            timestamp = bracketMatch[1];
        }
    }

    // Message is the full line for now
    const message = line;

    return {
        service,
        level,
        timestamp,
        message,
        fullLine: line,
    };
}

function getLevelIcon(level: ParsedLog["level"]) {
    switch (level) {
        case "ERROR":
            return <AlertCircle className="h-4 w-4 text-red-500" />;
        case "WARN":
            return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
        case "INFO":
            return <Info className="h-4 w-4 text-blue-500" />;
        case "DEBUG":
            return <Bug className="h-4 w-4 text-gray-500" />;
        default:
            return <FileText className="h-4 w-4 text-gray-400" />;
    }
}

function getLevelBadgeVariant(
    level: ParsedLog["level"]
): "default" | "secondary" | "destructive" {
    switch (level) {
        case "ERROR":
            return "destructive";
        case "WARN":
            return "secondary";
        default:
            return "default";
    }
}

interface LogsCardProps {
    autoRefresh?: boolean;
}

export function LogsCard({ autoRefresh = false }: LogsCardProps) {
    const [levelFilter, setLevelFilter] = useState<string>("ALL");
    const [serviceFilter, setServiceFilter] = useState<string>("ALL");
    const [sortField, setSortField] = useState<"service" | "level" | "timestamp">("timestamp");
    const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");
    const [expandedRow, setExpandedRow] = useState<number | null>(null);

    // Fetch logs from all services
    const backendLogs = useServiceLogs("backend", true);
    const celeryWorkerLogs = useServiceLogs("celery_worker", true);
    const celeryBeatLogs = useServiceLogs("celery_beat", true);
    const frontendLogs = useServiceLogs("frontend", true);
    const redisLogs = useServiceLogs("redis", true);

    // Combine all logs
    const allLogs = useMemo(() => {
        const logs: ParsedLog[] = [];

        if (backendLogs.data?.lines) {
            logs.push(
                ...backendLogs.data.lines.map((line) => parseLogLine(line, "backend"))
            );
        }
        if (celeryWorkerLogs.data?.lines) {
            logs.push(
                ...celeryWorkerLogs.data.lines.map((line) =>
                    parseLogLine(line, "celery_worker")
                )
            );
        }
        if (celeryBeatLogs.data?.lines) {
            logs.push(
                ...celeryBeatLogs.data.lines.map((line) =>
                    parseLogLine(line, "celery_beat")
                )
            );
        }
        if (frontendLogs.data?.lines) {
            logs.push(
                ...frontendLogs.data.lines.map((line) => parseLogLine(line, "frontend"))
            );
        }
        if (redisLogs.data?.lines) {
            logs.push(
                ...redisLogs.data.lines.map((line) => parseLogLine(line, "redis"))
            );
        }

        return logs;
    }, [
        backendLogs.data,
        celeryWorkerLogs.data,
        celeryBeatLogs.data,
        frontendLogs.data,
        redisLogs.data,
    ]);

    // Filter logs
    const filteredLogs = useMemo(() => {
        let filtered = allLogs;

        if (levelFilter !== "ALL") {
            filtered = filtered.filter((log) => log.level === levelFilter);
        }

        if (serviceFilter !== "ALL") {
            filtered = filtered.filter((log) => log.service === serviceFilter);
        }

        return filtered;
    }, [allLogs, levelFilter, serviceFilter]);

    // Sort logs
    const sortedLogs = useMemo(() => {
        const sorted = [...filteredLogs];

        sorted.sort((a, b) => {
            let comparison = 0;

            switch (sortField) {
                case "service":
                    comparison = a.service.localeCompare(b.service);
                    break;
                case "level":
                    comparison = a.level.localeCompare(b.level);
                    break;
                case "timestamp":
                    // Put logs without timestamps at the end
                    if (!a.timestamp && !b.timestamp) comparison = 0;
                    else if (!a.timestamp) comparison = 1;
                    else if (!b.timestamp) comparison = -1;
                    else comparison = a.timestamp.localeCompare(b.timestamp);
                    break;
            }

            return sortDirection === "asc" ? comparison : -comparison;
        });

        return sorted;
    }, [filteredLogs, sortField, sortDirection]);

    const handleSort = (field: typeof sortField) => {
        if (sortField === field) {
            setSortDirection(sortDirection === "asc" ? "desc" : "asc");
        } else {
            setSortField(field);
            setSortDirection("asc");
        }
    };

    const isLoading =
        backendLogs.isLoading ||
        celeryWorkerLogs.isLoading ||
        celeryBeatLogs.isLoading ||
        frontendLogs.isLoading ||
        redisLogs.isLoading;

    const hasError =
        backendLogs.error ||
        celeryWorkerLogs.error ||
        celeryBeatLogs.error ||
        frontendLogs.error ||
        redisLogs.error;

    // Get log level counts for filter badges
    const logCounts = useMemo(() => {
        const counts: Record<string, number> = {
            ERROR: 0,
            WARN: 0,
            INFO: 0,
            DEBUG: 0,
            UNKNOWN: 0,
        };
        allLogs.forEach((log) => {
            counts[log.level] = (counts[log.level] || 0) + 1;
        });
        return counts;
    }, [allLogs]);

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
                            Aggregated logs from all services (last 100 lines per service)
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <Badge variant="outline">
                            {sortedLogs.length} / {allLogs.length} logs
                        </Badge>
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
                    <Select value={serviceFilter} onValueChange={setServiceFilter}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Services" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="ALL">All Services</SelectItem>
                            <SelectItem value="backend">Backend</SelectItem>
                            <SelectItem value="celery_worker">Celery Worker</SelectItem>
                            <SelectItem value="celery_beat">Celery Beat</SelectItem>
                            <SelectItem value="frontend">Frontend</SelectItem>
                            <SelectItem value="redis">Redis</SelectItem>
                        </SelectContent>
                    </Select>
                    <Select value={levelFilter} onValueChange={setLevelFilter}>
                        <SelectTrigger className="w-[180px]">
                            <SelectValue placeholder="All Levels" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="ALL">
                                All Levels ({allLogs.length})
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
                {hasError && (
                    <Alert variant="destructive" className="mb-4">
                        <AlertDescription>
                            Failed to load some logs. Check service status.
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

                {/* Logs table */}
                {!isLoading && (
                    <div className="rounded-md border">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="w-[50px]"></TableHead>
                                    <TableHead
                                        className="cursor-pointer hover:bg-muted/50"
                                        onClick={() => handleSort("service")}
                                    >
                                        <div className="flex items-center gap-1">
                                            Service
                                            {sortField === "service" &&
                                                (sortDirection === "asc" ? (
                                                    <ChevronUp className="h-4 w-4" />
                                                ) : (
                                                    <ChevronDown className="h-4 w-4" />
                                                ))}
                                        </div>
                                    </TableHead>
                                    <TableHead
                                        className="cursor-pointer hover:bg-muted/50"
                                        onClick={() => handleSort("level")}
                                    >
                                        <div className="flex items-center gap-1">
                                            Level
                                            {sortField === "level" &&
                                                (sortDirection === "asc" ? (
                                                    <ChevronUp className="h-4 w-4" />
                                                ) : (
                                                    <ChevronDown className="h-4 w-4" />
                                                ))}
                                        </div>
                                    </TableHead>
                                    <TableHead
                                        className="cursor-pointer hover:bg-muted/50"
                                        onClick={() => handleSort("timestamp")}
                                    >
                                        <div className="flex items-center gap-1">
                                            Timestamp
                                            {sortField === "timestamp" &&
                                                (sortDirection === "asc" ? (
                                                    <ChevronUp className="h-4 w-4" />
                                                ) : (
                                                    <ChevronDown className="h-4 w-4" />
                                                ))}
                                        </div>
                                    </TableHead>
                                    <TableHead>Message</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {sortedLogs.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={5} className="text-center py-8">
                                            <p className="text-muted-foreground">
                                                {levelFilter !== "ALL" || serviceFilter !== "ALL"
                                                    ? "No logs match the selected filters"
                                                    : "No logs available"}
                                            </p>
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    sortedLogs.map((log, idx) => (
                                        <Collapsible
                                            key={idx}
                                            open={expandedRow === idx}
                                            onOpenChange={(open) =>
                                                setExpandedRow(open ? idx : null)
                                            }
                                            asChild
                                        >
                                            <>
                                                <TableRow className="hover:bg-muted/50">
                                                    <TableCell>
                                                        <CollapsibleTrigger asChild>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="p-0 h-auto"
                                                            >
                                                                {expandedRow === idx ? (
                                                                    <ChevronDown className="h-4 w-4" />
                                                                ) : (
                                                                    <ChevronRight className="h-4 w-4" />
                                                                )}
                                                            </Button>
                                                        </CollapsibleTrigger>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline">
                                                            {log.service}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="flex items-center gap-2">
                                                            {getLevelIcon(log.level)}
                                                            <Badge
                                                                variant={getLevelBadgeVariant(
                                                                    log.level
                                                                )}
                                                            >
                                                                {log.level}
                                                            </Badge>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell className="font-mono text-xs">
                                                        {log.timestamp || "—"}
                                                    </TableCell>
                                                    <TableCell className="max-w-[500px] truncate">
                                                        {log.message}
                                                    </TableCell>
                                                </TableRow>
                                                <TableRow>
                                                    <TableCell colSpan={5} className="p-0">
                                                        <CollapsibleContent>
                                                            <div className="bg-gray-950 p-4 border-t">
                                                                <pre className="font-mono text-xs text-gray-300 whitespace-pre-wrap break-words">
                                                                    {log.fullLine}
                                                                </pre>
                                                            </div>
                                                        </CollapsibleContent>
                                                    </TableCell>
                                                </TableRow>
                                            </>
                                        </Collapsible>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

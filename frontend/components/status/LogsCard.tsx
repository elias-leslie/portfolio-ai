"use client";

import React, { useState, useMemo } from "react";
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
import { useServiceLogs } from "@/lib/hooks/useServiceLogs";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface ParsedLog {
    service: string;
    logFile: string;
    level: "ERROR" | "WARN" | "INFO" | "DEBUG" | "UNKNOWN";
    timestamp: string;
    message: string;
    fullLine: string;
}

const LOG_SERVICES = [
    "backend",
    "backend_error",
    "celery_worker",
    "celery_worker_error",
    "celery_beat",
    "celery_beat_error",
    "frontend",
    "frontend_error",
    "redis",
    "postgresql",
];

// Map service identifiers to actual log file names for display
const LOG_FILE_DISPLAY_NAMES: Record<string, string> = {
    "backend": "backend.log",
    "backend_error": "backend-error.log",
    "celery_worker": "celery-worker.log",
    "celery_worker_error": "celery-worker-error.log",
    "celery_beat": "celery-beat.log",
    "celery_beat_error": "celery-beat-error.log",
    "frontend": "frontend.log",
    "frontend_error": "frontend-error.log",
    "redis": "redis-server.log",
    "postgresql": "postgresql-16-main.log",
};

function getLogFileDisplayName(service: string): string {
    return LOG_FILE_DISPLAY_NAMES[service] || service;
}

/**
 * Combines multi-line log messages into single entries.
 * Continuation lines (lines that don't start with timestamp/level) are appended to previous message.
 */
function combineMultiLineMessages(lines: string[], service: string): string[] {
    if (!lines || lines.length === 0) return [];

    const combined: string[] = [];
    let currentMessage = "";

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // Check if this line starts a new log entry based on service-specific patterns
        const isNewEntry = (() => {
            // Celery error format: starts with [YYYY-MM-DD
            if (service.includes("celery") && service.includes("error")) {
                return /^\[(\d{4}-\d{2}-\d{2})/.test(trimmed);
            }
            // PostgreSQL format: starts with YYYY-MM-DD
            if (service === "postgresql") {
                return /^\d{4}-\d{2}-\d{2}/.test(trimmed);
            }
            // Redis format: starts with PID:ROLE
            if (service === "redis") {
                return /^\d+:\w+/.test(trimmed);
            }
            // Backend/uvicorn format: starts with INFO:/ERROR:/etc
            if (service.includes("backend")) {
                return /^(INFO|ERROR|WARNING|DEBUG):/.test(trimmed);
            }
            // Frontend format: starts with space + HTTP method or warning symbol
            if (service.includes("frontend")) {
                return /^\s*(GET|POST|PUT|DELETE|PATCH|⚠)/.test(trimmed);
            }
            // Celery worker (non-error): starts with spaces + dot or timestamp
            if (service.includes("celery_worker")) {
                return /^\s*\./.test(trimmed) || /^\d{4}-\d{2}-\d{2}/.test(trimmed);
            }
            // Default: any line with content is a new entry
            return trimmed.length > 0;
        })();

        if (isNewEntry) {
            // Save previous message if exists
            if (currentMessage) {
                combined.push(currentMessage);
            }
            // Start new message
            currentMessage = line;
        } else {
            // Continuation line - append to current message
            if (currentMessage) {
                currentMessage += " " + trimmed;
            } else {
                // Orphan continuation line (shouldn't happen, but handle it)
                currentMessage = line;
            }
        }
    }

    // Don't forget the last message
    if (currentMessage) {
        combined.push(currentMessage);
    }

    return combined;
}

function parseLogLine(line: string, service: string, logFile: string): ParsedLog {
    // Clean the line first (strip leading/trailing whitespace)
    const cleanLine = line.trim();

    let level: ParsedLog["level"] = "UNKNOWN";
    let timestamp = "";
    let message = cleanLine;

    // Service-specific parsing
    if (service === "celery_beat_error" || service === "celery_worker_error") {
        // Format: [2025-11-10 10:44:42,210: INFO/MainProcess] Message
        const celeryMatch = cleanLine.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[^:]*: (\w+)\/[^\]]+\] (.+)$/);
        if (celeryMatch) {
            timestamp = celeryMatch[1];
            const levelStr = celeryMatch[2].toUpperCase();
            level = ["ERROR", "WARN", "WARNING", "INFO", "DEBUG"].includes(levelStr)
                ? (levelStr === "WARNING" ? "WARN" : levelStr as ParsedLog["level"])
                : "INFO";
            message = celeryMatch[3];
        }
    } else if (service === "postgresql") {
        // Format: 2025-11-09 23:35:57 EST [1149] @ LOG:  message
        // More flexible regex to handle variations
        const pgMatch = cleanLine.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+\w+\s+\[[\d]+\]\s+@\s+(\w+):\s*(.+)$/);
        if (pgMatch) {
            timestamp = pgMatch[1];
            const levelStr = pgMatch[2].toUpperCase();
            level = levelStr === "LOG" ? "INFO" :
                    levelStr === "ERROR" ? "ERROR" :
                    levelStr === "WARNING" ? "WARN" :
                    levelStr === "HINT" ? "INFO" :
                    levelStr === "FATAL" ? "ERROR" : "INFO";
            message = pgMatch[3];
        }
    } else if (service === "redis") {
        // Format: 457035:C 10 Nov 2025 10:40:42.296 * message
        const redisMatch = cleanLine.match(/^\d+:\w+ (\d{2} \w+ \d{4} \d{2}:\d{2}:\d{2}\.\d+) [*#] (.+)$/);
        if (redisMatch) {
            timestamp = redisMatch[1];
            level = cleanLine.includes("#") ? "WARN" : "INFO";
            message = redisMatch[2];
        }
    } else if (service === "backend" || service === "backend_error") {
        // Uvicorn format: INFO:     192.168.8.128:50397 - "GET /path" 200
        const uvicornMatch = cleanLine.match(/^(INFO|ERROR|WARNING|DEBUG):\s+(.+)$/);
        if (uvicornMatch) {
            const levelStr = uvicornMatch[1].toUpperCase();
            level = ["ERROR", "WARN", "WARNING", "INFO", "DEBUG"].includes(levelStr)
                ? (levelStr === "WARNING" ? "WARN" : levelStr as ParsedLog["level"])
                : "INFO";
            message = uvicornMatch[2];
        } else {
            // Python logging format: 2025-11-10 10:45:44,848 - logger - LEVEL - message
            const pythonMatch = cleanLine.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - [^ ]+ - (\w+) - (.+)$/);
            if (pythonMatch) {
                timestamp = pythonMatch[1];
                const levelStr = pythonMatch[2].toUpperCase();
                level = ["ERROR", "WARN", "WARNING", "INFO", "DEBUG"].includes(levelStr)
                    ? (levelStr === "WARNING" ? "WARN" : levelStr as ParsedLog["level"])
                    : "INFO";
                message = pythonMatch[3];
            }
        }
    } else if (service === "frontend" || service === "frontend_error") {
        // Format: GET / 200 in 29ms (compile: 1870µs, render: 27ms)
        // Or: ⚠ Cross origin request detected...
        // Frontend logs don't have explicit timestamps in the log lines
        if (cleanLine.match(/^\s*(GET|POST|PUT|DELETE|PATCH)\s+.+\s+\d{3}\s+in\s+\d+ms/)) {
            level = "INFO";
            message = cleanLine.trim();
        } else if (cleanLine.match(/^\s*⚠/)) {
            level = "WARN";
            message = cleanLine.trim();
        } else if (cleanLine.match(/^\s*✓/)) {
            level = "INFO";
            message = cleanLine.trim();
        } else if (cleanLine.trim().length > 0) {
            // Generic frontend log line
            level = "INFO";
            message = cleanLine.trim();
        }
    } else if (service === "celery_worker") {
        // Celery worker task list format: "  . task_name"
        // Or timestamped entries
        if (cleanLine.match(/^\s*\.\s+\w+/)) {
            level = "INFO";
            message = cleanLine.trim();
        } else if (cleanLine.match(/^\[\d{4}-\d{2}-\d{2}/)) {
            // Timestamped celery worker logs (same format as error logs)
            const celeryMatch = cleanLine.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})[^:]*: (\w+)\/[^\]]+\] (.+)$/);
            if (celeryMatch) {
                timestamp = celeryMatch[1];
                const levelStr = celeryMatch[2].toUpperCase();
                level = ["ERROR", "WARN", "WARNING", "INFO", "DEBUG"].includes(levelStr)
                    ? (levelStr === "WARNING" ? "WARN" : levelStr as ParsedLog["level"])
                    : "INFO";
                message = celeryMatch[3];
            }
        }
    }

    // Fallback: try generic patterns if service-specific parsing didn't work
    if (timestamp === "") {
        // Try ISO8601 or similar
        const isoMatch = cleanLine.match(/(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)/);
        if (isoMatch) {
            timestamp = isoMatch[1].replace(',', '.');
        }
    }

    if (level === "UNKNOWN") {
        // Try to find level keywords
        if (/ERROR|FATAL|CRITICAL/i.test(cleanLine)) {
            level = "ERROR";
        } else if (/WARN(ING)?/i.test(cleanLine)) {
            level = "WARN";
        } else if (/INFO/i.test(cleanLine)) {
            level = "INFO";
        } else if (/DEBUG|TRACE/i.test(cleanLine)) {
            level = "DEBUG";
        }
    }

    // Truncate message for display (full line available in fullLine)
    const truncatedMessage = message.length > 200 ? message.substring(0, 200) + "..." : message;

    return {
        service,
        logFile,
        level,
        timestamp,
        message: truncatedMessage,
        fullLine: cleanLine,
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
    const [displayLimit, setDisplayLimit] = useState(25);

    // Fetch logs from all services
    const backendLogs = useServiceLogs("backend", true);
    const backendErrorLogs = useServiceLogs("backend_error", true);
    const celeryWorkerLogs = useServiceLogs("celery_worker", true);
    const celeryWorkerErrorLogs = useServiceLogs("celery_worker_error", true);
    const celeryBeatLogs = useServiceLogs("celery_beat", true);
    const celeryBeatErrorLogs = useServiceLogs("celery_beat_error", true);
    const frontendLogs = useServiceLogs("frontend", true);
    const frontendErrorLogs = useServiceLogs("frontend_error", true);
    const redisLogs = useServiceLogs("redis", true);
    const postgresqlLogs = useServiceLogs("postgresql", true);

    // Combine all logs
    const allLogs = useMemo(() => {
        const logs: ParsedLog[] = [];

        const logSources = [
            { data: backendLogs.data, service: "backend" },
            { data: backendErrorLogs.data, service: "backend_error" },
            { data: celeryWorkerLogs.data, service: "celery_worker" },
            { data: celeryWorkerErrorLogs.data, service: "celery_worker_error" },
            { data: celeryBeatLogs.data, service: "celery_beat" },
            { data: celeryBeatErrorLogs.data, service: "celery_beat_error" },
            { data: frontendLogs.data, service: "frontend" },
            { data: frontendErrorLogs.data, service: "frontend_error" },
            { data: redisLogs.data, service: "redis" },
            { data: postgresqlLogs.data, service: "postgresql" },
        ];

        logSources.forEach(({ data, service }) => {
            if (data?.lines) {
                const logFile = data.log_file || getLogFileDisplayName(service);
                // Combine multi-line messages first
                const combinedLines = combineMultiLineMessages(data.lines, service);
                logs.push(...combinedLines.map((line) => parseLogLine(line, service, logFile)));
            }
        });

        return logs;
    }, [
        backendLogs.data,
        backendErrorLogs.data,
        celeryWorkerLogs.data,
        celeryWorkerErrorLogs.data,
        celeryBeatLogs.data,
        celeryBeatErrorLogs.data,
        frontendLogs.data,
        frontendErrorLogs.data,
        redisLogs.data,
        postgresqlLogs.data,
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
        backendErrorLogs.isLoading ||
        celeryWorkerLogs.isLoading ||
        celeryWorkerErrorLogs.isLoading ||
        celeryBeatLogs.isLoading ||
        celeryBeatErrorLogs.isLoading ||
        frontendLogs.isLoading ||
        frontendErrorLogs.isLoading ||
        redisLogs.isLoading ||
        postgresqlLogs.isLoading;

    const hasError =
        backendLogs.error ||
        backendErrorLogs.error ||
        celeryWorkerLogs.error ||
        celeryWorkerErrorLogs.error ||
        celeryBeatLogs.error ||
        celeryBeatErrorLogs.error ||
        frontendLogs.error ||
        frontendErrorLogs.error ||
        redisLogs.error ||
        postgresqlLogs.error;

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
                            <SelectItem value="backend">{getLogFileDisplayName("backend")}</SelectItem>
                            <SelectItem value="backend_error">{getLogFileDisplayName("backend_error")}</SelectItem>
                            <SelectItem value="celery_worker">{getLogFileDisplayName("celery_worker")}</SelectItem>
                            <SelectItem value="celery_worker_error">{getLogFileDisplayName("celery_worker_error")}</SelectItem>
                            <SelectItem value="celery_beat">{getLogFileDisplayName("celery_beat")}</SelectItem>
                            <SelectItem value="celery_beat_error">{getLogFileDisplayName("celery_beat_error")}</SelectItem>
                            <SelectItem value="frontend">{getLogFileDisplayName("frontend")}</SelectItem>
                            <SelectItem value="frontend_error">{getLogFileDisplayName("frontend_error")}</SelectItem>
                            <SelectItem value="redis">{getLogFileDisplayName("redis")}</SelectItem>
                            <SelectItem value="postgresql">{getLogFileDisplayName("postgresql")}</SelectItem>
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
                    <>
                        <div className="rounded-md border max-h-[600px] overflow-auto">
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
                                    sortedLogs.slice(0, displayLimit).map((log, idx) => (
                                        <React.Fragment key={idx}>
                                            <TableRow className="hover:bg-muted/50">
                                                <TableCell>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="p-0 h-auto"
                                                        onClick={() =>
                                                            setExpandedRow(
                                                                expandedRow === idx ? null : idx
                                                            )
                                                        }
                                                    >
                                                        {expandedRow === idx ? (
                                                            <ChevronDown className="h-4 w-4" />
                                                        ) : (
                                                            <ChevronRight className="h-4 w-4" />
                                                        )}
                                                    </Button>
                                                </TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline" className="font-mono text-xs">
                                                            {log.logFile}
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
                                                {expandedRow === idx && (
                                                    <TableRow>
                                                        <TableCell colSpan={5} className="p-0">
                                                            <div className="bg-gray-950 p-4 border-t">
                                                                <pre className="font-mono text-xs text-gray-300 whitespace-pre-wrap break-words">
                                                                    {log.fullLine}
                                                                </pre>
                                                            </div>
                                                        </TableCell>
                                                    </TableRow>
                                                )}
                                        </React.Fragment>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </div>
                    {sortedLogs.length > displayLimit && (
                        <div className="mt-4 flex justify-center">
                            <Button
                                variant="outline"
                                onClick={() => setDisplayLimit(displayLimit + 25)}
                            >
                                Show More ({sortedLogs.length - displayLimit} remaining)
                            </Button>
                        </div>
                    )}
                    {displayLimit > 25 && sortedLogs.length <= displayLimit && (
                        <div className="mt-4 flex justify-center">
                            <Button variant="outline" onClick={() => setDisplayLimit(25)}>
                                Show Less
                            </Button>
                        </div>
                    )}
                </>
                )}
            </CardContent>
        </Card>
    );
}

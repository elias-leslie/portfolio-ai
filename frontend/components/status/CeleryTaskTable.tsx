"use client";

import { useState } from "react";
import { RefreshCw, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { useCeleryTasks } from "@/lib/hooks/useCeleryTasks";
import type { TaskInfo } from "@/lib/api/celery";

export function CeleryTaskTable() {
  const [filter, setFilter] = useState<"all" | "active" | "pending" | "completed" | "failed">("all");
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const { data, refetch, isLoading, isFetching } = useCeleryTasks(filter);

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case "ACTIVE":
        return (
          <Badge className="bg-blue-500 text-white animate-pulse">
            Active
          </Badge>
        );
      case "PENDING":
        return (
          <Badge variant="secondary" className="bg-yellow-500 text-white">
            Pending
          </Badge>
        );
      case "SUCCESS":
        return (
          <Badge variant="default" className="bg-green-500 text-white">
            Completed
          </Badge>
        );
      case "FAILURE":
        return (
          <Badge variant="destructive">
            Failed
          </Badge>
        );
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return "-";
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  };

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return "-";
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header with filter and refresh */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h3 className="text-lg font-semibold">Celery Tasks</h3>
          {data && (
            <div className="text-sm text-muted-foreground">
              {data.total} total ({data.active_count} active, {data.pending_count} pending)
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Select value={filter} onValueChange={(v: any) => setFilter(v)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Tasks</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
              <SelectItem value="failed">Failed</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isLoading || isFetching}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Task table */}
      {!data && !isLoading ? (
        <div className="text-center py-8 text-muted-foreground">
          Click Refresh to load Celery tasks
        </div>
      ) : isLoading ? (
        <div className="text-center py-8 text-muted-foreground">
          Loading tasks...
        </div>
      ) : data && data.tasks.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground">
          No tasks found
        </div>
      ) : data ? (
        <div className="border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]"></TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Task Name</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Worker</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.tasks.map((task: TaskInfo) => (
                <>
                  <TableRow key={task.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell onClick={() => toggleRow(task.id)}>
                      {expandedRows.has(task.id) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell>{getStatusBadge(task.status)}</TableCell>
                    <TableCell className="font-mono text-sm">{task.name}</TableCell>
                    <TableCell className="text-sm">{formatTimestamp(task.started_at || task.date_done)}</TableCell>
                    <TableCell className="text-sm">{formatDuration(task.duration)}</TableCell>
                    <TableCell className="text-sm">{task.worker || "-"}</TableCell>
                  </TableRow>
                  {expandedRows.has(task.id) && (
                    <TableRow key={`${task.id}-details`}>
                      <TableCell colSpan={6} className="bg-muted/20">
                        <div className="p-4 space-y-2 text-sm">
                          <div>
                            <span className="font-semibold">Task ID:</span> {task.id}
                          </div>
                          {task.args && (
                            <div>
                              <span className="font-semibold">Args:</span>{" "}
                              <code className="bg-muted px-1 rounded">{task.args}</code>
                            </div>
                          )}
                          {task.kwargs && (
                            <div>
                              <span className="font-semibold">Kwargs:</span>{" "}
                              <code className="bg-muted px-1 rounded">{task.kwargs}</code>
                            </div>
                          )}
                          {task.result && (
                            <div>
                              <span className="font-semibold">Result:</span>{" "}
                              <pre className="bg-muted p-2 rounded mt-1 overflow-x-auto">
                                {task.result}
                              </pre>
                            </div>
                          )}
                          {task.traceback && (
                            <div>
                              <span className="font-semibold text-destructive">Error:</span>{" "}
                              <pre className="bg-destructive/10 p-2 rounded mt-1 overflow-x-auto text-destructive">
                                {task.traceback}
                              </pre>
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : null}
    </div>
  );
}

"use client";

import { Handle, Position, type NodeProps, useViewport } from "@xyflow/react";
import { useState, memo } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { NodeData } from "@/lib/api/workflows";

const statusColors: Record<NodeData["status"], string> = {
  running: "bg-primary animate-pulse",
  completed: "bg-green-500", // Keep specific green for success
  failed: "bg-destructive",
  pending: "bg-yellow-500",
  idle: "bg-muted-foreground",
};

const statusLabels: Record<NodeData["status"], string> = {
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  pending: "Pending",
  idle: "Idle",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function formatTimeAgo(isoDate: string | null): string {
  if (!isoDate) return "Never";
  const date = new Date(isoDate);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

function TaskNodeComponent({ data }: NodeProps) {
  const nodeData = data as unknown as NodeData;
  const { label, schedule, status, successRate, avgDuration, lastRun, nextRun, populatesTables } =
    nodeData;
  const { zoom } = useViewport();
  const [isHovered, setIsHovered] = useState(false);

  const scale = isHovered ? Math.max(1.5, 1 / zoom) : 1;

  return (
    <TooltipProvider>
      <div
        className={cn(
          "rounded-lg border border-border shadow-sm min-w-[180px] max-w-[200px]",
          "transition-all duration-300 ease-in-out hover:z-50 hover:shadow-xl origin-center",
          "bg-card text-card-foreground",
          status === "running" && "ring-2 ring-primary ring-offset-2 ring-offset-background",
          (status === "failed" || successRate < 50) && "ring-2 ring-destructive ring-offset-2 ring-offset-background",
          (status !== "failed" && status !== "running" && successRate >= 50 && successRate < 80) && "ring-2 ring-yellow-500 ring-offset-2 ring-offset-background"
        )}
        style={{
          transform: `scale(${scale})`,
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Left handle for incoming edges */}
        <Handle
          type="target"
          position={Position.Left}
          className="!bg-muted-foreground !border-background !w-3 !h-3"
        />

        {/* Header */}
        <div className="px-3 py-2 border-b border-border bg-muted/50 rounded-t-lg">
          <div className="flex items-center gap-2">
            <div className={cn("w-2 h-2 rounded-full shrink-0", statusColors[status])} />
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-sm font-medium truncate cursor-default">{label}</span>
              </TooltipTrigger>
              <TooltipContent>
                <p>{label}</p>
                <p className="text-xs text-muted-foreground">{statusLabels[status]}</p>
              </TooltipContent>
            </Tooltip>
          </div>
          <Badge variant="outline" className="mt-1 text-[10px] h-5">
            {schedule}
          </Badge>
        </div>

        {/* Metrics */}
        <div className="px-3 py-2 space-y-1 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Success</span>
            <span
              className={cn(
                "font-medium",
                successRate >= 90 && "text-green-600 dark:text-green-400",
                successRate >= 70 && successRate < 90 && "text-yellow-600 dark:text-yellow-400",
                successRate < 70 && "text-red-600 dark:text-red-400"
              )}
            >
              {successRate.toFixed(0)}%
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Duration</span>
            <span className="font-medium">{formatDuration(avgDuration)}</span>
          </div>
          <div className="flex justify-between items-center text-[10px]">
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-muted-foreground cursor-default">
                  Last: {formatTimeAgo(lastRun)}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                {lastRun ? new Date(lastRun).toLocaleString() : "Never run"}
              </TooltipContent>
            </Tooltip>
          </div>
          {populatesTables && populatesTables.length > 0 && (
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="text-[10px] text-muted-foreground truncate cursor-default">
                  → {populatesTables.slice(0, 2).join(", ")}
                  {populatesTables.length > 2 && ` +${populatesTables.length - 2}`}
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-medium">Populates tables:</p>
                <ul className="text-xs">
                  {populatesTables.map((t) => (
                    <li key={t}>{t}</li>
                  ))}
                </ul>
              </TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Right handle for outgoing edges */}
        <Handle
          type="source"
          position={Position.Right}
          className="!bg-muted-foreground !border-background !w-3 !h-3"
        />
      </div>
    </TooltipProvider>
  );
}

export const TaskNode = memo(TaskNodeComponent);

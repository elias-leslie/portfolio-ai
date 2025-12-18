"use client";

import { useState, useMemo, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Clock,
  Play,
  CheckCircle,
  XCircle,
  Calendar,
  Zap,
  Timer,
  AlertCircle,
  Folder,
  FolderOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useBeatSchedule, useCeleryTasks } from "@/lib/hooks/useCeleryTasks";
import type { ScheduleInfo, TaskInfo, TaskListResponse } from "@/lib/api/celery";
import { cn } from "@/lib/utils";

interface TaskGroup {
  name: string;
  displayName: string;
  tasks: ScheduleInfo[];
  expanded: boolean;
}

type SelectedItem =
  | { type: "group"; group: TaskGroup }
  | { type: "task"; task: ScheduleInfo; group: TaskGroup }
  | null;

/**
 * Extract category from task name
 * e.g., "app.tasks.strategy.generate_daily_signals" -> "strategy"
 * e.g., "calculate_fear_greed_daily" -> "calculate"
 */
function getTaskCategory(taskName: string): string {
  // Handle full module path: app.tasks.category.function
  if (taskName.includes(".")) {
    const parts = taskName.split(".");
    // Find "tasks" and get next segment
    const tasksIdx = parts.indexOf("tasks");
    if (tasksIdx >= 0 && parts[tasksIdx + 1]) {
      return parts[tasksIdx + 1];
    }
    // Fallback to second-to-last segment
    return parts[parts.length - 2] || "other";
  }

  // Handle simple names: verb_noun_suffix -> verb
  const parts = taskName.split("_");
  if (parts.length > 1) {
    // Check for common action verbs
    const verb = parts[0].toLowerCase();
    if (
      ["calculate", "check", "refresh", "update", "ingest", "archive", "generate", "evaluate", "auto"].includes(
        verb
      )
    ) {
      return verb;
    }
    // If starts with symbol-like pattern, group as "symbol"
    if (parts[0].match(/^[A-Z]{2,5}$/)) {
      return "symbol-specific";
    }
  }

  return "other";
}

/**
 * Get display name for category
 */
function getCategoryDisplayName(category: string): string {
  const displayNames: Record<string, string> = {
    strategy: "📊 Strategy",
    ingestion: "📥 Data Ingestion",
    calculate: "🧮 Calculations",
    check: "✅ Health Checks",
    refresh: "🔄 Refresh",
    update: "⬆️ Updates",
    ingest: "📥 Ingestion",
    archive: "📦 Archive",
    generate: "⚡ Generation",
    evaluate: "📈 Evaluation",
    auto: "🤖 Automation",
    "symbol-specific": "📌 Symbol Specific",
    other: "📁 Other",
  };
  return displayNames[category] || `📁 ${category.charAt(0).toUpperCase() + category.slice(1)}`;
}

/**
 * Parse schedule string to human-readable format
 */
function parseSchedule(schedule: string): { type: string; description: string } {
  if (schedule.startsWith("<crontab:")) {
    // Extract crontab parts: <crontab: M H dM MY d (m/h/dM/MY/d)>
    const match = schedule.match(/<crontab: ([^>]+)>/);
    if (match) {
      const parts = match[1].split(" ");
      if (parts.length >= 2) {
        const [minute, hour] = parts;
        if (hour === "*") {
          return { type: "hourly", description: `Every hour at :${minute.padStart(2, "0")}` };
        }
        return { type: "daily", description: `Daily at ${hour}:${minute.padStart(2, "0")}` };
      }
    }
    return { type: "cron", description: schedule };
  }
  if (schedule.toLowerCase().startsWith("every")) {
    return { type: "interval", description: schedule };
  }
  return { type: "unknown", description: schedule };
}

export function TasksExplorerTab() {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(["strategy", "check"]));
  const [selectedItem, setSelectedItem] = useState<SelectedItem>(null);

  // Fetch schedule data (on-demand)
  const { data: scheduleData, isLoading: scheduleLoading, refetch: refetchSchedule, isFetching } = useBeatSchedule();

  // Fetch task execution data (on-demand)
  const {
    data: tasksData,
    isLoading: tasksLoading,
    refetch: refetchTasks,
    isFetching: tasksFetching,
  } = useCeleryTasks("all", 100);

  // Build task groups from schedule data
  const taskGroups = useMemo<TaskGroup[]>(() => {
    if (!scheduleData) return [];

    const groupMap = new Map<string, ScheduleInfo[]>();

    scheduleData.forEach((task) => {
      const category = getTaskCategory(task.task);
      if (!groupMap.has(category)) {
        groupMap.set(category, []);
      }
      groupMap.get(category)!.push(task);
    });

    // Sort groups by size (largest first) and alphabetically within size
    return Array.from(groupMap.entries())
      .sort((a, b) => {
        if (b[1].length !== a[1].length) return b[1].length - a[1].length;
        return a[0].localeCompare(b[0]);
      })
      .map(([name, tasks]) => ({
        name,
        displayName: getCategoryDisplayName(name),
        tasks: tasks.sort((a, b) => a.name.localeCompare(b.name)),
        expanded: expandedGroups.has(name),
      }));
  }, [scheduleData, expandedGroups]);

  // Get task execution info by name
  const getTaskExecution = useCallback(
    (taskName: string): TaskInfo | undefined => {
      if (!tasksData?.tasks) return undefined;
      // Match by task name (could be full or short name)
      return tasksData.tasks.find((t) => t.name.includes(taskName) || taskName.includes(t.name.split(".").pop() || ""));
    },
    [tasksData]
  );

  const toggleGroup = (groupName: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupName)) {
        next.delete(groupName);
      } else {
        next.add(groupName);
      }
      return next;
    });
  };

  const handleRefresh = async () => {
    await Promise.all([refetchSchedule(), refetchTasks()]);
  };

  const isLoading = scheduleLoading || tasksLoading;
  const isRefreshing = isFetching || tasksFetching;

  return (
    <div className="h-[calc(100vh-280px)] min-h-[500px]">
      <ResizablePanelGroup orientation="horizontal" className="rounded-lg border bg-surface">
        {/* Left Panel: Task Explorer Tree */}
        <ResizablePanel defaultSize={35} minSize={25} maxSize={50}>
          <div className="flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-text">Scheduled Tasks</h3>
                {scheduleData && (
                  <Badge variant="secondary" className="text-xs">
                    {scheduleData.length}
                  </Badge>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isLoading || isRefreshing}
              >
                <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
              </Button>
            </div>

            {/* Tree */}
            <ScrollArea className="flex-1">
              {!scheduleData && !isLoading ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Calendar className="mb-2 h-8 w-8" />
                  <p className="text-sm">Click refresh to load schedules</p>
                </div>
              ) : isLoading ? (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <RefreshCw className="mb-2 h-8 w-8 animate-spin" />
                  <p className="text-sm">Loading...</p>
                </div>
              ) : (
                <div className="p-2">
                  {taskGroups.map((group) => (
                    <div key={group.name} className="mb-1">
                      {/* Group Header */}
                      <button
                        onClick={() => {
                          toggleGroup(group.name);
                          setSelectedItem({ type: "group", group });
                        }}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted",
                          selectedItem?.type === "group" &&
                            selectedItem.group.name === group.name &&
                            "bg-muted"
                        )}
                      >
                        {expandedGroups.has(group.name) ? (
                          <ChevronDown className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        )}
                        {expandedGroups.has(group.name) ? (
                          <FolderOpen className="h-4 w-4 text-muted-foreground" />
                        ) : (
                          <Folder className="h-4 w-4 text-muted-foreground" />
                        )}
                        <span className="flex-1 truncate font-medium">{group.displayName}</span>
                        <Badge variant="outline" className="text-xs">
                          {group.tasks.length}
                        </Badge>
                      </button>

                      {/* Group Tasks */}
                      {expandedGroups.has(group.name) && (
                        <div className="ml-6 mt-1 space-y-0.5">
                          {group.tasks.map((task) => {
                            const execution = getTaskExecution(task.task);
                            return (
                              <button
                                key={task.name}
                                onClick={() => setSelectedItem({ type: "task", task, group })}
                                className={cn(
                                  "flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-sm transition-colors hover:bg-muted",
                                  selectedItem?.type === "task" &&
                                    selectedItem.task.name === task.name &&
                                    "bg-muted"
                                )}
                              >
                                <TaskStatusIcon status={execution?.status} />
                                <span className="flex-1 truncate">{task.name}</span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Right Panel: Details */}
        <ResizablePanel defaultSize={65}>
          <div className="flex h-full flex-col">
            {selectedItem === null ? (
              <div className="flex flex-1 flex-col items-center justify-center text-muted-foreground">
                <Zap className="mb-2 h-12 w-12" />
                <p className="text-sm">Select a task or group to view details</p>
              </div>
            ) : selectedItem.type === "group" ? (
              <GroupDetailsPanel group={selectedItem.group} tasksData={tasksData} />
            ) : (
              <TaskDetailsPanel
                task={selectedItem.task}
                group={selectedItem.group}
                execution={getTaskExecution(selectedItem.task.task)}
              />
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}

function TaskStatusIcon({ status }: { status?: string }) {
  if (!status) {
    return <Clock className="h-3.5 w-3.5 text-muted-foreground" />;
  }

  switch (status.toUpperCase()) {
    case "ACTIVE":
      return <Play className="h-3.5 w-3.5 text-info animate-pulse" />;
    case "PENDING":
      return <Clock className="h-3.5 w-3.5 text-warning" />;
    case "SUCCESS":
      return <CheckCircle className="h-3.5 w-3.5 text-gain" />;
    case "FAILURE":
      return <XCircle className="h-3.5 w-3.5 text-loss" />;
    default:
      return <AlertCircle className="h-3.5 w-3.5 text-muted-foreground" />;
  }
}

function GroupDetailsPanel({
  group,
  tasksData,
}: {
  group: TaskGroup;
  tasksData?: TaskListResponse;
}) {
  // Calculate group stats
  const stats = useMemo(() => {
    const taskNames = group.tasks.map((t) => t.task);
    const executions = tasksData?.tasks.filter((t) =>
      taskNames.some((name) => t.name.includes(name) || name.includes(t.name.split(".").pop() || ""))
    );

    return {
      total: group.tasks.length,
      active: executions?.filter((e) => e.status === "ACTIVE").length || 0,
      success: executions?.filter((e) => e.status === "SUCCESS").length || 0,
      failed: executions?.filter((e) => e.status === "FAILURE").length || 0,
    };
  }, [group, tasksData]);

  return (
    <div className="flex flex-col p-6">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-text">{group.displayName}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {group.tasks.length} scheduled {group.tasks.length === 1 ? "task" : "tasks"}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="mb-6 grid grid-cols-4 gap-4">
        <StatCard
          label="Total"
          value={stats.total}
          icon={<Calendar className="h-4 w-4" />}
          className="border-border"
        />
        <StatCard
          label="Active"
          value={stats.active}
          icon={<Play className="h-4 w-4" />}
          className="border-info/30 bg-info/5"
        />
        <StatCard
          label="Success"
          value={stats.success}
          icon={<CheckCircle className="h-4 w-4" />}
          className="border-gain/30 bg-gain/5"
        />
        <StatCard
          label="Failed"
          value={stats.failed}
          icon={<XCircle className="h-4 w-4" />}
          className="border-loss/30 bg-loss/5"
        />
      </div>

      {/* Task List */}
      <div className="rounded-lg border">
        <div className="border-b bg-muted/50 px-4 py-2 text-sm font-medium">Tasks in Group</div>
        <ScrollArea className="max-h-[300px]">
          <div className="divide-y">
            {group.tasks.map((task) => {
              const schedule = parseSchedule(task.schedule);
              return (
                <div key={task.name} className="flex items-center justify-between px-4 py-2.5">
                  <div>
                    <p className="text-sm font-medium">{task.name}</p>
                    <p className="text-xs text-muted-foreground">{task.task}</p>
                  </div>
                  <Badge variant="outline" className="text-xs">
                    {schedule.description}
                  </Badge>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

function TaskDetailsPanel({
  task,
  group,
  execution,
}: {
  task: ScheduleInfo;
  group: TaskGroup;
  execution?: TaskInfo;
}) {
  const schedule = parseSchedule(task.schedule);

  return (
    <ScrollArea className="h-full">
      <div className="p-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2">
            <TaskStatusIcon status={execution?.status} />
            <h2 className="text-xl font-semibold text-text">{task.name}</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{task.task}</p>
          <Badge variant="secondary" className="mt-2">
            {group.displayName}
          </Badge>
        </div>

        {/* Schedule Info */}
        <div className="mb-6 rounded-lg border p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-muted-foreground">
            <Clock className="h-4 w-4" />
            Schedule
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Type</span>
              <Badge variant="outline">{schedule.type}</Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">Schedule</span>
              <span className="font-medium">{schedule.description}</span>
            </div>
            {task.lastRun && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Last Run</span>
                <span className="font-medium">{new Date(task.lastRun).toLocaleString()}</span>
              </div>
            )}
            {task.nextRun && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Next Run</span>
                <span className="font-medium">{new Date(task.nextRun).toLocaleString()}</span>
              </div>
            )}
          </div>
        </div>

        {/* Execution Info */}
        {execution && (
          <div className="mb-6 rounded-lg border p-4">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-muted-foreground">
              <Timer className="h-4 w-4" />
              Last Execution
            </h3>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Status</span>
                <ExecutionStatusBadge status={execution.status} />
              </div>
              {execution.startedAt && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Started</span>
                  <span className="font-medium">{new Date(execution.startedAt).toLocaleString()}</span>
                </div>
              )}
              {execution.duration !== null && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Duration</span>
                  <span className="font-medium">{formatDuration(execution.duration)}</span>
                </div>
              )}
              {execution.worker && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Worker</span>
                  <span className="font-mono text-xs">{execution.worker.split("@")[0]}</span>
                </div>
              )}
            </div>

            {/* Result */}
            {execution.result && (
              <div className="mt-4">
                <p className="mb-1 text-xs font-semibold uppercase text-gain">Result</p>
                <pre className="max-h-[200px] overflow-auto rounded-md bg-gain/5 p-2 text-xs font-mono">
                  {execution.result}
                </pre>
              </div>
            )}

            {/* Error */}
            {execution.traceback && (
              <div className="mt-4">
                <p className="mb-1 text-xs font-semibold uppercase text-loss">Error</p>
                <pre className="max-h-[200px] overflow-auto rounded-md bg-loss/5 p-2 text-xs font-mono text-loss">
                  {execution.traceback}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Raw Schedule */}
        <div className="rounded-lg border p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-muted-foreground">
            <Zap className="h-4 w-4" />
            Raw Configuration
          </h3>
          <pre className="overflow-auto rounded-md bg-muted p-2 text-xs font-mono">
            {JSON.stringify(task, null, 2)}
          </pre>
        </div>
      </div>
    </ScrollArea>
  );
}

function ExecutionStatusBadge({ status }: { status: string }) {
  switch (status.toUpperCase()) {
    case "ACTIVE":
      return (
        <Badge className="bg-info text-info-foreground animate-pulse">Active</Badge>
      );
    case "PENDING":
      return <Badge className="bg-warning text-warning-foreground">Pending</Badge>;
    case "SUCCESS":
      return <Badge className="bg-gain text-white">Success</Badge>;
    case "FAILURE":
      return <Badge className="bg-loss text-white">Failed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function StatCard({
  label,
  value,
  icon,
  className,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border p-3", className)}>
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs uppercase">{label}</span>
      </div>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

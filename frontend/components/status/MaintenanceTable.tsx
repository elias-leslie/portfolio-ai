"use client";

import React, { useState, useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
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
import {
  RefreshCw,
  PlayCircle,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  ShieldAlert,
  ArrowUpDown,
} from "lucide-react";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import { ServiceActionDialog } from "./ServiceActionDialog";
import { TaskResultDisplay, BatchResultsDialog, type BatchResult } from "./MaintenanceDialogs";
import {
  triggerMaintenanceTask,
  cleanupOldNews,
  vacuumDatabase,
  validateIntegrity,
  type MaintenanceResult,
} from "@/lib/api/maintenance";
import { useMaintenanceData } from "@/lib/hooks/useMaintenanceData";
import { useMaintenanceBackupCheck } from "@/lib/hooks/useMaintenanceBackupCheck";
import { toast } from "sonner";
import {
  TASK_CONFIGS,
  getTaskIcon,
  type TaskCategory,
  type TaskConfig,
} from "./maintenanceTaskConfig";

// Unified task interface
interface MaintenanceTask {
  id: string;
  name: string;
  category: TaskCategory;
  icon: React.ReactNode;
  sizeMb: number | null;
  fileCount: number | null;
  schedule: string;
  retentionPolicy: string | null;
  lastRun: MaintenanceResult | null;
  path: string | null;
  description: string | null;
  taskName: string; // Celery task name
  isDbTask?: boolean; // Database tasks need special handling
  supportsDryRun?: boolean; // Only some tasks support dryRun
}

// Sort configuration
type SortKey = "name" | "category" | "sizeMb" | "fileCount" | "schedule" | "lastRun";
type SortDirection = "asc" | "desc";

export function MaintenanceTable() {
  // Use the maintenance data hook
  const {
    fileCleanup,
    lastRunSummary,
    diskSpace,
    dbSize,
    schedule,
    cacheStatus,
    isLoading,
    isRefreshing,
    refresh: fetchAllData,
  } = useMaintenanceData();

  // Additional local state
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);

  // Backup check hook
  const { backupCheck, isCheckingBackup } = useMaintenanceBackupCheck(dryRun);
  const [categoryFilter, setCategoryFilter] = useState<TaskCategory | "all">("all");
  const [sortKey, setSortKey] = useState<SortKey>("category");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  // Dialog state
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string;
    description: string;
    actionLabel: string;
    onConfirm: () => void;
    storageKey?: string;
  } | null>(null);

  // Task result dialog (single task)
  const [taskResultOpen, setTaskResultOpen] = useState(false);
  const [taskResult, setTaskResult] = useState<{
    taskName: string;
    dryRun: boolean;
    result: Record<string, unknown> | null;
  } | null>(null);

  // Batch results dialog (Run All)
  const [batchResultsOpen, setBatchResultsOpen] = useState(false);
  const [batchResults, setBatchResults] = useState<BatchResult[]>([]);
  const [isRunningAll, setIsRunningAll] = useState(false);

  const handleRefresh = () => {
    fetchAllData();
  };

  // Build unified task list from config
  const tasks: MaintenanceTask[] = useMemo(() => {
    const getLastRun = (taskName: string) => lastRunSummary?.tasks?.[taskName] || null;

    // Factory function to create task from config
    const createTask = (config: TaskConfig): MaintenanceTask | null => {
      // Get file cleanup data if applicable
      let sizeMb: number | null = null;
      let fileCount: number | null = null;
      let path: string | null = null;
      let scheduleOverride: string | undefined;
      let retentionOverride: string | undefined;

      if (config.fileCleanupKey && fileCleanup) {
        const data = fileCleanup[config.fileCleanupKey];
        if (data) {
          sizeMb = data.sizeMb;
          fileCount = data.fileCount;
          path = data.path;
          scheduleOverride = data.schedule;
          retentionOverride = data.retentionPolicy;
        }
      }

      // Get cache status data for dev_caches task
      if (config.id === "dev_caches" && cacheStatus) {
        sizeMb = cacheStatus.totalSizeMb;
        fileCount = cacheStatus.totalFileCount;
      }

      // Skip file cleanup tasks if data not available
      if (config.fileCleanupKey && !fileCleanup) return null;
      if (config.id === "dev_caches" && !cacheStatus) return null;

      // Get last run with fallback
      const lastRun = getLastRun(config.taskName) ||
        (config.fallbackTaskName ? getLastRun(config.fallbackTaskName) : null);

      return {
        id: config.id,
        name: config.name,
        category: config.category,
        icon: getTaskIcon(config),
        sizeMb,
        fileCount,
        schedule: scheduleOverride || config.schedule,
        retentionPolicy: retentionOverride ?? config.retentionPolicy,
        lastRun,
        path,
        description: config.description,
        taskName: config.taskName,
        isDbTask: config.isDbTask,
        supportsDryRun: config.supportsDryRun,
      };
    };

    return TASK_CONFIGS
      .map(createTask)
      .filter((task): task is MaintenanceTask => task !== null);
  }, [fileCleanup, cacheStatus, lastRunSummary]);

  // Filter and sort tasks
  const filteredTasks = useMemo(() => {
    let result = [...tasks];

    // Apply category filter
    if (categoryFilter !== "all") {
      result = result.filter((t) => t.category === categoryFilter);
    }

    // Apply sorting
    result.sort((a, b) => {
      let comparison = 0;
      switch (sortKey) {
        case "name":
          comparison = a.name.localeCompare(b.name);
          break;
        case "category":
          comparison = a.category.localeCompare(b.category);
          break;
        case "sizeMb":
          comparison = (a.sizeMb ?? -1) - (b.sizeMb ?? -1);
          break;
        case "fileCount":
          comparison = (a.fileCount ?? -1) - (b.fileCount ?? -1);
          break;
        case "schedule":
          comparison = a.schedule.localeCompare(b.schedule);
          break;
        case "lastRun":
          const aTime = a.lastRun?.startedAt ? new Date(a.lastRun.startedAt).getTime() : 0;
          const bTime = b.lastRun?.startedAt ? new Date(b.lastRun.startedAt).getTime() : 0;
          comparison = aTime - bTime;
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });

    return result;
  }, [tasks, categoryFilter, sortKey, sortDirection]);

  // Toggle sort
  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  // File cleanup trigger handler
  const handleFileCleanupTrigger = async (taskName: string, supportsDryRun: boolean = false) => {
    setTriggeringTask(taskName);
    const useDryRun = dryRun && supportsDryRun;
    try {
      const result = await triggerMaintenanceTask(taskName, {
        dryRun: useDryRun,
        waitForResult: true,
        timeout: 60,
      });

      if (result.result) {
        setTaskResult({
          taskName,
          dryRun: useDryRun,
          result: result.result as Record<string, unknown>,
        });
        setTaskResultOpen(true);
      }

      const isDry = useDryRun ? " (dry run)" : "";
      if (result.status === "completed") {
        toast.success(`${taskName}${isDry}: ${result.message}`);
      } else if (result.status === "timeout") {
        toast.warning(`${taskName}${isDry}: Still running...`);
      } else {
        toast.success(result.message);
      }

      if (!useDryRun) {
        setTimeout(fetchAllData, 2000);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to trigger task";
      toast.error(`Failed to trigger ${taskName}: ${message}`);
    } finally {
      setTriggeringTask(null);
    }
  };

  // Database task handlers
  const shouldShowDialog = (storageKey: string, isLiveOperation: boolean) => {
    if (typeof window === "undefined") return true;
    if (isLiveOperation) return true;
    return !localStorage.getItem(storageKey);
  };

  const handleCleanupNews = async () => {
    setTriggeringTask("cleanup_news");
    try {
      const result = await cleanupOldNews(dryRun);
      toast.success(`Cleanup ${result.status}: ${result.summary?.deleted || 0} articles ${dryRun ? "would be" : ""} deleted`);
      await fetchAllData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed";
      toast.error(`Cleanup failed: ${message}`);
    } finally {
      setTriggeringTask(null);
    }
  };

  const handleVacuumDatabase = async () => {
    setTriggeringTask("vacuum_database");
    try {
      const result = await vacuumDatabase(dryRun);
      toast.success(`Vacuum ${result.status}: ${result.summary?.totalReclaimedMb || 0} MB ${dryRun ? "could be" : ""} reclaimed`);
      await fetchAllData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed";
      toast.error(`Vacuum failed: ${message}`);
    } finally {
      setTriggeringTask(null);
    }
  };

  const handleValidateIntegrity = async () => {
    setTriggeringTask("validate_integrity");
    try {
      const result = await validateIntegrity(dryRun);
      const summary = result.summary as Record<string, unknown> | null;
      const totalErrors = typeof summary?.totalErrors === "number" ? summary.totalErrors : 0;
      const totalWarnings = typeof summary?.totalWarnings === "number" ? summary.totalWarnings : 0;
      toast.success(`Validation ${result.status}: ${totalErrors} errors, ${totalWarnings} warnings`);
      await fetchAllData();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed";
      toast.error(`Validation failed: ${message}`);
    } finally {
      setTriggeringTask(null);
    }
  };

  // Trigger task with appropriate handler
  const triggerTask = (task: MaintenanceTask) => {
    const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.canProceed;

    if (liveBlocked && task.isDbTask) {
      toast.error(`Cannot run: ${backupCheck?.blockingReason}`);
      return;
    }

    // Database tasks have special handlers
    if (task.id === "cleanup_news") {
      const storageKey = "status.confirm.cleanupNews";
      if (shouldShowDialog(storageKey, !dryRun)) {
        setActionDialogConfig({
          title: "Cleanup Old News",
          description: dryRun
            ? "Preview articles older than 90 days that would be deleted."
            : "Permanently delete news articles older than 90 days.",
          actionLabel: dryRun ? "Preview" : "Delete",
          onConfirm: handleCleanupNews,
          storageKey: dryRun ? storageKey : undefined,
        });
        setActionDialogOpen(true);
      } else {
        handleCleanupNews();
      }
    } else if (task.id === "vacuum_db") {
      const storageKey = "status.confirm.vacuumDatabase";
      if (shouldShowDialog(storageKey, !dryRun)) {
        setActionDialogConfig({
          title: "Vacuum Database",
          description: dryRun
            ? "Analyze tables and show potential space savings."
            : "Optimize all database tables using VACUUM ANALYZE.",
          actionLabel: dryRun ? "Analyze" : "Vacuum",
          onConfirm: handleVacuumDatabase,
          storageKey: dryRun ? storageKey : undefined,
        });
        setActionDialogOpen(true);
      } else {
        handleVacuumDatabase();
      }
    } else if (task.id === "validate_integrity") {
      const storageKey = "status.confirm.validateIntegrity";
      if (shouldShowDialog(storageKey, !dryRun)) {
        setActionDialogConfig({
          title: "Validate Integrity",
          description: dryRun
            ? "Check for orphaned records and consistency issues."
            : "Check and attempt to fix integrity issues.",
          actionLabel: dryRun ? "Check" : "Fix",
          onConfirm: handleValidateIntegrity,
          storageKey: dryRun ? storageKey : undefined,
        });
        setActionDialogOpen(true);
      } else {
        handleValidateIntegrity();
      }
    } else {
      // Regular file/data cleanup tasks
      handleFileCleanupTrigger(task.taskName, task.supportsDryRun ?? false);
    }
  };

  // Run all tasks and collect results
  const handleRunAll = async () => {
    setIsRunningAll(true);
    setBatchResults([]);
    const results: typeof batchResults = [];

    for (const task of filteredTasks) {
      // In dry run mode, SKIP tasks that don't support dryRun
      if (dryRun && !task.supportsDryRun) {
        results.push({
          taskName: task.name,
          taskId: task.taskName,
          status: "success",
          result: { skipped: true, reason: "Task does not support dry run preview" },
        });
        continue;
      }

      setTriggeringTask(task.taskName);

      try {
        let taskResult: Record<string, unknown> | null = null;

        // Handle special DB tasks that use scripts endpoint
        if (task.id === "cleanup_news") {
          const r = await cleanupOldNews(dryRun);
          taskResult = { ...r, ...r.summary };
        } else if (task.id === "vacuum_db") {
          const r = await vacuumDatabase(dryRun);
          taskResult = { ...r, ...r.summary };
        } else if (task.id === "validate_integrity") {
          const r = await validateIntegrity(dryRun);
          taskResult = { ...r, ...r.summary };
        } else {
          // Regular Celery tasks
          const result = await triggerMaintenanceTask(task.taskName, {
            dryRun: dryRun,
            waitForResult: true,
            timeout: 60,
          });
          taskResult = result.result as Record<string, unknown> | null;
        }

        results.push({
          taskName: task.name,
          taskId: task.taskName,
          status: "success",
          result: taskResult,
        });
      } catch (error) {
        results.push({
          taskName: task.name,
          taskId: task.taskName,
          status: "error",
          result: null,
          error: error instanceof Error ? error.message : "Unknown error",
        });
      }
    }

    setTriggeringTask(null);
    setIsRunningAll(false);
    setBatchResults(results);
    setBatchResultsOpen(true);

    // Refresh data after run (if not dry run)
    if (!dryRun) {
      setTimeout(fetchAllData, 2000);
    }
  };

  // Format helpers
  const formatSize = (mb: number | null) => {
    if (mb === null) return "—";
    if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${mb.toFixed(1)} MB`;
  };

  const formatLastRun = (lastRun: MaintenanceResult | null) => {
    if (!lastRun?.startedAt) return "—";
    const date = new Date(lastRun.startedAt);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return "Just now";
  };

  const getStatusIcon = (lastRun: MaintenanceResult | null) => {
    if (!lastRun) return null;
    switch (lastRun.status) {
      case "success":
        return <CheckCircle2 className="h-3.5 w-3.5 text-status-success" />;
      case "error":
        return <AlertCircle className="h-3.5 w-3.5 text-status-error" />;
      case "running":
        return <RefreshCw className="h-3.5 w-3.5 animate-spin text-status-info" />;
      default:
        return null;
    }
  };

  const getCategoryBadge = (category: TaskCategory) => {
    const colors: Record<TaskCategory, string> = {
      file: "bg-status-warning/20 text-status-warning",
      cache: "bg-status-warning/20 text-status-warning",
      data: "bg-status-info/20 text-status-info",
      database: "bg-accent/20 text-accent",
      system: "bg-surface-muted text-text-muted",
    };
    const labels: Record<TaskCategory, string> = {
      file: "File",
      cache: "Cache",
      data: "Data",
      database: "DB",
      system: "System",
    };
    return (
      <Badge variant="outline" className={`text-xs ${colors[category]}`}>
        {labels[category]}
      </Badge>
    );
  };

  // Summary stats
  const getSummary = () => {
    if (isLoading) return "Loading...";
    if (diskSpace?.alerts?.length) return `${diskSpace.alerts.length} disk alert(s)`;
    return `${tasks.length} tasks ready`;
  };

  const canRunLive = !dryRun && backupCheck?.canProceed === true;
  const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.canProceed;

  return (
    <>
      <ExpandableCard
        title="Maintenance"
        description="System cleanup, database maintenance, and scheduled tasks"
        summary={getSummary()}
        defaultCollapsed
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {/* Dry Run Toggle */}
            <div className="flex items-center gap-2">
              <Switch id="dry-run-table" checked={dryRun} onCheckedChange={setDryRun} />
              <Label htmlFor="dry-run-table" className="cursor-pointer text-sm">
                Dry Run
              </Label>
            </div>

            {/* Backup Status (when live mode) */}
            {!dryRun && (
              <div className="flex items-center gap-1.5">
                {isCheckingBackup ? (
                  <Badge variant="secondary" className="flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Checking...
                  </Badge>
                ) : canRunLive ? (
                  <Badge variant="default" className="flex items-center gap-1 bg-status-success">
                    <ShieldCheck className="h-3 w-3" />
                    Backup OK
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="flex items-center gap-1">
                    <ShieldAlert className="h-3 w-3" />
                    {backupCheck?.blockingReason?.split(".")[0] || "No backup"}
                  </Badge>
                )}
              </div>
            )}

            {/* Run All Button */}
            <Button
              size="sm"
              variant="default"
              onClick={handleRunAll}
              disabled={isRunningAll || liveBlocked}
              title={dryRun ? "Preview all tasks (dry run)" : "Execute all tasks"}
            >
              {isRunningAll ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  Running {filteredTasks.findIndex(t => t.taskName === triggeringTask) + 1}/{filteredTasks.length}...
                </>
              ) : (
                <>
                  <PlayCircle className="h-4 w-4 mr-1" />
                  {dryRun ? "Run All (Preview)" : "Run All"}
                </>
              )}
            </Button>

            {/* Refresh Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              title="Refresh all data"
            >
              <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
            </Button>
          </div>
        }
      >
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary Stats */}
            <div className="grid grid-cols-4 gap-4 p-4 bg-surface-muted/30 rounded-lg">
              <div className="text-center">
                <div className="text-xl font-bold">{formatSize(fileCleanup?.totalSizeMb || 0)}</div>
                <div className="text-xs text-muted-foreground">Managed Files</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold">{formatSize(dbSize?.databaseSizeMb || 0)}</div>
                <div className="text-xs text-muted-foreground">Database</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold">{formatSize(cacheStatus?.totalSizeMb || 0)}</div>
                <div className="text-xs text-muted-foreground">Dev Caches</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold">
                  {diskSpace?.partitions?.[0]?.usedPercentage?.toFixed(0) || "—"}%
                </div>
                <div className="text-xs text-muted-foreground">Disk Used</div>
              </div>
            </div>

            {/* Filter */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Filter:</span>
              <Select
                value={categoryFilter}
                onValueChange={(v) => setCategoryFilter(v as TaskCategory | "all")}
              >
                <SelectTrigger className="w-32 h-8">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All ({tasks.length})</SelectItem>
                  <SelectItem value="file">File ({tasks.filter((t) => t.category === "file").length})</SelectItem>
                  <SelectItem value="cache">Cache ({tasks.filter((t) => t.category === "cache").length})</SelectItem>
                  <SelectItem value="data">Data ({tasks.filter((t) => t.category === "data").length})</SelectItem>
                  <SelectItem value="database">Database ({tasks.filter((t) => t.category === "database").length})</SelectItem>
                  <SelectItem value="system">System ({tasks.filter((t) => t.category === "system").length})</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Table */}
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent">
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort("name")}
                  >
                    <div className="flex items-center gap-1">
                      Task
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort("category")}
                  >
                    <div className="flex items-center gap-1">
                      Category
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none text-right"
                    onClick={() => toggleSort("sizeMb")}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Size
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none text-right"
                    onClick={() => toggleSort("fileCount")}
                  >
                    <div className="flex items-center justify-end gap-1">
                      Files
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead>Retention</TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort("schedule")}
                  >
                    <div className="flex items-center gap-1">
                      Schedule
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead
                    className="cursor-pointer select-none"
                    onClick={() => toggleSort("lastRun")}
                  >
                    <div className="flex items-center gap-1">
                      Last Run
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                  <TableHead className="w-12 text-center">Run</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredTasks.map((task) => (
                  <TableRow key={task.id} className="group">
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {task.icon}
                        <span className="font-medium">{task.name}</span>
                      </div>
                    </TableCell>
                    <TableCell>{getCategoryBadge(task.category)}</TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {formatSize(task.sizeMb)}
                    </TableCell>
                    <TableCell className="text-right font-mono text-xs">
                      {task.fileCount?.toLocaleString() ?? "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {task.retentionPolicy ?? "—"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {task.schedule}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5">
                        {getStatusIcon(task.lastRun)}
                        <span className="text-xs text-muted-foreground">
                          {formatLastRun(task.lastRun)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        onClick={() => triggerTask(task)}
                        disabled={triggeringTask === task.taskName || (liveBlocked && task.isDbTask)}
                        title={`Run ${task.name}`}
                      >
                        {triggeringTask === task.taskName ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <PlayCircle className="h-4 w-4" />
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* Scheduled Tasks Summary */}
            <div className="text-xs text-muted-foreground text-center pt-2 border-t">
              {schedule?.totalCount || 0} scheduled maintenance tasks configured
            </div>
          </div>
        )}
      </ExpandableCard>

      {/* Confirmation Dialog */}
      {actionDialogConfig && (
        <ServiceActionDialog
          open={actionDialogOpen}
          onOpenChange={setActionDialogOpen}
          title={actionDialogConfig.title}
          description={actionDialogConfig.description}
          actionLabel={actionDialogConfig.actionLabel}
          onConfirm={actionDialogConfig.onConfirm}
          storageKey={actionDialogConfig.storageKey}
        />
      )}

      {/* Task Results Dialog */}
      {taskResult && (
        <ServiceActionDialog
          open={taskResultOpen}
          onOpenChange={setTaskResultOpen}
          title={`${taskResult.dryRun ? "Dry Run Preview" : "Task Complete"}: ${taskResult.taskName.replace(/_/g, " ")}`}
          description={taskResult.dryRun ? "No changes were made. Review what would happen below." : "Task completed. See results below."}
          actionLabel="Done"
          onConfirm={() => setTaskResultOpen(false)}
        >
          <div className="my-4 max-h-80 overflow-auto border rounded p-3 bg-muted/30">
            {taskResult.result && (
              <TaskResultDisplay result={taskResult.result} />
            )}
          </div>
        </ServiceActionDialog>
      )}

      {/* Batch Results Dialog (Run All) */}
      <BatchResultsDialog
        open={batchResultsOpen}
        onOpenChange={setBatchResultsOpen}
        dryRun={dryRun}
        results={batchResults}
      />
    </>
  );
}

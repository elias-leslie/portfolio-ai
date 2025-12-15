"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  FolderOpen,
  FileText,
  Database,
  Brain,
  TestTube,
  RefreshCw,
  PlayCircle,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Trash2,
  ShieldCheck,
  ShieldAlert,
  HardDrive,
  Zap,
  Users,
  ServerCrash,
  FileX,
  Camera,
  ArrowUpDown,
  RotateCcw,
} from "lucide-react";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import { ServiceActionDialog } from "./ServiceActionDialog";
import {
  getFileCleanupStatus,
  triggerMaintenanceTask,
  cleanupOldNews,
  vacuumDatabase,
  validateIntegrity,
  getMaintenanceLastRun,
  getMaintenanceDiskSpace,
  getMaintenanceDatabaseSize,
  getMaintenanceSchedule,
  checkBackupRequirements,
  getCacheStatus,
  type FileCleanupStatusResponse,
  type MaintenanceResult,
  type LastRunSummary,
  type DiskSpaceResponse,
  type DatabaseSizeResponse,
  type MaintenanceScheduleResponse,
  type BackupRequirementCheck,
  type CacheStatusResponse,
} from "@/lib/api/maintenance";
import { toast } from "sonner";

// Task category types
type TaskCategory = "file" | "cache" | "data" | "database" | "system";

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
  supportsDryRun?: boolean; // Only some tasks support dry_run
}

// Sort configuration
type SortKey = "name" | "category" | "sizeMb" | "fileCount" | "schedule" | "lastRun";
type SortDirection = "asc" | "desc";

export function MaintenanceTable() {
  // State for all data sources
  const [fileCleanup, setFileCleanup] = useState<FileCleanupStatusResponse | null>(null);
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(null);
  const [diskSpace, setDiskSpace] = useState<DiskSpaceResponse | null>(null);
  const [dbSize, setDbSize] = useState<DatabaseSizeResponse | null>(null);
  const [schedule, setSchedule] = useState<MaintenanceScheduleResponse | null>(null);
  const [backupCheck, setBackupCheck] = useState<BackupRequirementCheck | null>(null);
  const [cacheStatus, setCacheStatus] = useState<CacheStatusResponse | null>(null);

  // UI state
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [isCheckingBackup, setIsCheckingBackup] = useState(false);
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
  const [batchResults, setBatchResults] = useState<Array<{
    taskName: string;
    taskId: string;
    status: "success" | "error" | "timeout";
    result: Record<string, unknown> | null;
    error?: string;
  }>>([]);
  const [isRunningAll, setIsRunningAll] = useState(false);

  // Fetch all data
  const fetchAllData = useCallback(async () => {
    try {
      const [fileData, lastRun, diskData, dbData, scheduleData, cacheData] = await Promise.all([
        getFileCleanupStatus(),
        getMaintenanceLastRun(),
        getMaintenanceDiskSpace(),
        getMaintenanceDatabaseSize(),
        getMaintenanceSchedule(),
        getCacheStatus(),
      ]);
      setFileCleanup(fileData);
      setLastRunSummary(lastRun);
      setDiskSpace(diskData);
      setDbSize(dbData);
      setSchedule(scheduleData);
      setCacheStatus(cacheData);
    } catch (error) {
      console.error("Failed to fetch maintenance data:", error);
      toast.error("Failed to load maintenance data");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  // Check backup when dry-run is toggled off
  useEffect(() => {
    if (!dryRun) {
      checkBackupStatus();
    } else {
      setBackupCheck(null);
    }
  }, [dryRun]);

  const checkBackupStatus = async () => {
    setIsCheckingBackup(true);
    try {
      const check = await checkBackupRequirements(24, true);
      setBackupCheck(check);
      if (!check.can_proceed) {
        toast.warning(`Backup check: ${check.blocking_reason || "Requirements not met"}`);
      }
    } catch {
      toast.error("Could not verify backup status");
      setBackupCheck({
        backup_exists: false,
        backup_recent: false,
        backup_verified: false,
        backup_name: null,
        backup_age_hours: null,
        can_proceed: false,
        blocking_reason: "Could not verify backup status",
        warnings: [],
      });
    } finally {
      setIsCheckingBackup(false);
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    fetchAllData();
  };

  // Build unified task list
  const tasks: MaintenanceTask[] = useMemo(() => {
    const taskList: MaintenanceTask[] = [];

    // File cleanup tasks
    if (fileCleanup) {
      taskList.push({
        id: "logs",
        name: "Application Logs",
        category: "file",
        icon: <FileText className="h-4 w-4 text-orange-500" />,
        sizeMb: fileCleanup.logs.size_mb,
        fileCount: fileCleanup.logs.file_count,
        schedule: fileCleanup.logs.schedule,
        retentionPolicy: fileCleanup.logs.retention_policy,
        lastRun: null,
        path: fileCleanup.logs.path,
        description: "Application log files",
        taskName: "cleanup_old_logs_task",
        supportsDryRun: true,
      });
      taskList.push({
        id: "backups",
        name: "Database Backups",
        category: "file",
        icon: <Database className="h-4 w-4 text-blue-500" />,
        sizeMb: fileCleanup.backups.size_mb,
        fileCount: fileCleanup.backups.file_count,
        schedule: fileCleanup.backups.schedule,
        retentionPolicy: fileCleanup.backups.retention_policy,
        lastRun: null,
        path: fileCleanup.backups.path,
        description: "PostgreSQL backup files",
        taskName: "cleanup_old_backups_task",
        supportsDryRun: true,
      });
      taskList.push({
        id: "models",
        name: "ML Model Versions",
        category: "file",
        icon: <Brain className="h-4 w-4 text-purple-500" />,
        sizeMb: fileCleanup.models.size_mb,
        fileCount: fileCleanup.models.file_count,
        schedule: fileCleanup.models.schedule,
        retentionPolicy: fileCleanup.models.retention_policy,
        lastRun: null,
        path: fileCleanup.models.path,
        description: "Trained ML model files",
        taskName: "cleanup_old_models_task",
        supportsDryRun: true,
      });
      taskList.push({
        id: "solution_state",
        name: "Test Artifacts",
        category: "file",
        icon: <TestTube className="h-4 w-4 text-green-500" />,
        sizeMb: fileCleanup.solution_state.size_mb,
        fileCount: fileCleanup.solution_state.file_count,
        schedule: fileCleanup.solution_state.schedule,
        retentionPolicy: fileCleanup.solution_state.retention_policy,
        lastRun: null,
        path: fileCleanup.solution_state.path,
        description: "UI regression test artifacts",
        taskName: "cleanup_solution_state_task",
        supportsDryRun: true,
      });
    }

    // Cache cleanup (manual only)
    if (cacheStatus) {
      taskList.push({
        id: "dev_caches",
        name: "Dev Caches",
        category: "cache",
        icon: <Zap className="h-4 w-4 text-yellow-500" />,
        sizeMb: cacheStatus.total_size_mb,
        fileCount: cacheStatus.total_file_count,
        schedule: "Manual",
        retentionPolicy: "Auto-regenerate",
        lastRun: null,
        path: null,
        description: "Python bytecode, linter caches, build caches",
        taskName: "cleanup_cache_directories_task",
        supportsDryRun: true,
      });
    }

    // Data cleanup tasks
    taskList.push({
      id: "agent_runs",
      name: "Old Agent Runs",
      category: "data",
      icon: <Users className="h-4 w-4 text-indigo-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Weekly Sun 04:15",
      retentionPolicy: "30 days",
      lastRun: null,
      path: null,
      description: "Historical agent execution records",
      taskName: "cleanup_old_agent_runs_task",
      supportsDryRun: true,
    });
    taskList.push({
      id: "orphaned_data",
      name: "Orphaned Data",
      category: "data",
      icon: <ServerCrash className="h-4 w-4 text-red-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Weekly Sun 04:30",
      retentionPolicy: "Integrity fix",
      lastRun: null,
      path: null,
      description: "Records without valid foreign keys",
      taskName: "cleanup_orphaned_data_task",
      supportsDryRun: true,
    });
    taskList.push({
      id: "temp_files",
      name: "Temp Files",
      category: "data",
      icon: <FileX className="h-4 w-4 text-gray-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Daily 02:15",
      retentionPolicy: "24 hours",
      lastRun: null,
      path: null,
      description: "Temporary processing files",
      taskName: "cleanup_temp_files_task",
      supportsDryRun: true,
    });
    taskList.push({
      id: "evidence",
      name: "Evidence Artifacts",
      category: "data",
      icon: <Camera className="h-4 w-4 text-cyan-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Daily 06:00",
      retentionPolicy: "5 versions",
      lastRun: null,
      path: null,
      description: "Feature verification screenshots",
      taskName: "cleanup_old_versions",
      supportsDryRun: true,
    });
    taskList.push({
      id: "debug_captures",
      name: "Debug Captures",
      category: "data",
      icon: <Camera className="h-4 w-4 text-gray-400" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Daily 06:00",
      retentionPolicy: "7 days",
      lastRun: null,
      path: null,
      description: "Debug screenshots and traces",
      taskName: "cleanup_debug_captures",
      supportsDryRun: true,
    });

    // Database maintenance tasks
    taskList.push({
      id: "cleanup_news",
      name: "Old News",
      category: "database",
      icon: <Trash2 className="h-4 w-4 text-orange-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Daily 03:00",
      retentionPolicy: "90 days",
      lastRun: lastRunSummary?.cleanup_news || null,
      path: null,
      description: "Delete news articles older than 90 days",
      taskName: "cleanup_old_news_task",
      isDbTask: true,
      supportsDryRun: true,
    });
    taskList.push({
      id: "vacuum_db",
      name: "Vacuum Database",
      category: "database",
      icon: <Database className="h-4 w-4 text-blue-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Weekly Sun 05:30",
      retentionPolicy: null,
      lastRun: lastRunSummary?.vacuum_database || null,
      path: null,
      description: "Reclaim space and update statistics",
      taskName: "vacuum_database_task",
      isDbTask: true,
      supportsDryRun: true,
    });
    taskList.push({
      id: "validate_integrity",
      name: "Validate Integrity",
      category: "database",
      icon: <CheckCircle2 className="h-4 w-4 text-green-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Daily 04:00",
      retentionPolicy: null,
      lastRun: lastRunSummary?.validate_integrity || null,
      path: null,
      description: "Check for orphaned records and consistency",
      taskName: "validate_integrity_task",
      isDbTask: true,
      supportsDryRun: true,
    });

    // System tasks
    taskList.push({
      id: "rotate_logs",
      name: "Rotate Logs",
      category: "system",
      icon: <RotateCcw className="h-4 w-4 text-slate-500" />,
      sizeMb: null,
      fileCount: null,
      schedule: "Daily 01:00",
      retentionPolicy: null,
      lastRun: null,
      path: null,
      description: "Archive and compress old log files",
      taskName: "rotate_logs_task",
      supportsDryRun: true,
    });

    return taskList;
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
          const aTime = a.lastRun?.started_at ? new Date(a.lastRun.started_at).getTime() : 0;
          const bTime = b.lastRun?.started_at ? new Date(b.lastRun.started_at).getTime() : 0;
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
      toast.success(`Vacuum ${result.status}: ${result.summary?.total_reclaimed_mb || 0} MB ${dryRun ? "could be" : ""} reclaimed`);
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
      const totalErrors = typeof summary?.total_errors === "number" ? summary.total_errors : 0;
      const totalWarnings = typeof summary?.total_warnings === "number" ? summary.total_warnings : 0;
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
    const canRunLive = !dryRun && backupCheck?.can_proceed === true;
    const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.can_proceed;

    if (liveBlocked && task.isDbTask) {
      toast.error(`Cannot run: ${backupCheck?.blocking_reason}`);
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
      // In dry run mode, SKIP tasks that don't support dry_run
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
    if (!lastRun?.started_at) return "—";
    const date = new Date(lastRun.started_at);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    return "Just now";
  };

  const getStatusIcon = (lastRun: MaintenanceResult | null) => {
    if (!lastRun) return null;
    switch (lastRun.status) {
      case "success":
        return <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />;
      case "error":
        return <AlertCircle className="h-3.5 w-3.5 text-red-500" />;
      case "running":
        return <RefreshCw className="h-3.5 w-3.5 animate-spin text-blue-500" />;
      default:
        return null;
    }
  };

  const getCategoryBadge = (category: TaskCategory) => {
    const colors: Record<TaskCategory, string> = {
      file: "bg-orange-500/20 text-orange-400",
      cache: "bg-yellow-500/20 text-yellow-400",
      data: "bg-blue-500/20 text-blue-400",
      database: "bg-purple-500/20 text-purple-400",
      system: "bg-slate-500/20 text-slate-400",
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

  const canRunLive = !dryRun && backupCheck?.can_proceed === true;
  const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.can_proceed;

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
                  <Badge variant="default" className="flex items-center gap-1 bg-green-600">
                    <ShieldCheck className="h-3 w-3" />
                    Backup OK
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="flex items-center gap-1">
                    <ShieldAlert className="h-3 w-3" />
                    {backupCheck?.blocking_reason?.split(".")[0] || "No backup"}
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
                <div className="text-xl font-bold">{formatSize(fileCleanup?.total_size_mb || 0)}</div>
                <div className="text-xs text-muted-foreground">Managed Files</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold">{formatSize(dbSize?.database_size_mb || 0)}</div>
                <div className="text-xs text-muted-foreground">Database</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold">{formatSize(cacheStatus?.total_size_mb || 0)}</div>
                <div className="text-xs text-muted-foreground">Dev Caches</div>
              </div>
              <div className="text-center">
                <div className="text-xl font-bold">
                  {diskSpace?.partitions?.[0]?.used_percentage?.toFixed(0) || "—"}%
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
              {schedule?.total_count || 0} scheduled maintenance tasks configured
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
            <div className="space-y-2 text-sm">
              {taskResult.result && Object.entries(taskResult.result).map(([key, value]) => {
                if (key === "task_id" || key === "success") return null;
                if (key === "details" && Array.isArray(value) && value.length > 0) {
                  return (
                    <details key={key} className="border rounded p-2 bg-background">
                      <summary className="cursor-pointer font-medium">
                        Details ({value.length} items)
                      </summary>
                      <div className="mt-2 space-y-1 pl-2 max-h-40 overflow-auto">
                        {value.slice(0, 50).map((item, idx) => (
                          <div key={idx} className="text-xs text-muted-foreground font-mono truncate">
                            {typeof item === "object" ? JSON.stringify(item) : String(item)}
                          </div>
                        ))}
                        {value.length > 50 && (
                          <div className="text-xs text-muted-foreground italic">
                            ... and {value.length - 50} more
                          </div>
                        )}
                      </div>
                    </details>
                  );
                }
                if (key === "details" && Array.isArray(value) && value.length === 0) return null;
                return (
                  <div key={key} className="flex justify-between py-1 border-b border-border/30 last:border-0">
                    <span className="text-muted-foreground capitalize">{key.replace(/_/g, " ")}:</span>
                    <span className="font-mono font-medium">
                      {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </ServiceActionDialog>
      )}

      {/* Batch Results Dialog (Run All) */}
      <Dialog open={batchResultsOpen} onOpenChange={setBatchResultsOpen}>
        <DialogContent className="!max-w-[90vw] !w-[1400px] max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="text-xl">
              {dryRun ? "Maintenance Dry Run Report" : "Maintenance Execution Report"}
            </DialogTitle>
            <DialogDescription>
              {dryRun
                ? "Preview of what would happen. No changes were made."
                : "Summary of executed maintenance tasks."}
              {" • "}{batchResults.length} tasks • {batchResults.filter(r => r.status === "success").length} success • {batchResults.filter(r => r.status === "error").length} errors
            </DialogDescription>
          </DialogHeader>

          <ScrollArea className="flex-1 min-h-0 pr-4">
            <div className="space-y-4 py-4">
              {batchResults.map((result, idx) => (
                <details
                  key={idx}
                  className={`border rounded-lg ${
                    result.status === "error"
                      ? "border-red-500/50 bg-red-500/5"
                      : result.status === "timeout"
                      ? "border-yellow-500/50 bg-yellow-500/5"
                      : "border-green-500/50 bg-green-500/5"
                  }`}
                >
                  <summary className="flex items-center gap-2 p-3 cursor-pointer select-none hover:bg-white/5">
                    {result.status === "success" ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500 flex-shrink-0" />
                    ) : result.status === "error" ? (
                      <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
                    ) : (
                      <Loader2 className="h-5 w-5 text-yellow-500 flex-shrink-0" />
                    )}
                    <span className="font-semibold">{result.taskName}</span>
                    <Badge
                      variant={result.status === "success" ? "default" : "destructive"}
                      className={result.status === "success" ? "bg-green-600" : ""}
                    >
                      {result.status}
                    </Badge>
                    {result.error && (
                      <span className="text-red-400 text-xs ml-2 truncate">{result.error.slice(0, 50)}...</span>
                    )}
                  </summary>

                  <div className="px-4 pb-4">
                    {result.error && (
                      <div className="text-red-400 text-sm mb-2 font-mono">
                        Error: {result.error}
                      </div>
                    )}

                    {result.result && (
                      <div className="space-y-2">
                      {Object.entries(result.result).map(([key, value]) => {
                        // Skip internal fields
                        if (key === "task_id" || key === "success" || key === "dry_run") return null;

                        // Handle arrays (like file lists) - render as table
                        if (Array.isArray(value)) {
                          if (value.length === 0) return null;

                          // Get columns from first object item, or just show values
                          const firstItem = value[0];
                          const isObjectArray = typeof firstItem === "object" && firstItem !== null;
                          const columns = isObjectArray ? Object.keys(firstItem) : null;

                          return (
                            <div key={key} className="border-t border-border/30 pt-2">
                              <div className="text-sm font-medium capitalize mb-2">
                                {key.replace(/_/g, " ")} ({value.length} items)
                              </div>
                              <div className="bg-background/50 rounded max-h-72 overflow-auto">
                                {isObjectArray && columns ? (
                                  <table className="w-full text-xs">
                                    <thead className="sticky top-0 bg-background border-b">
                                      <tr>
                                        {columns.map(col => (
                                          <th key={col} className="text-left p-2 font-medium capitalize">
                                            {col.replace(/_/g, " ")}
                                          </th>
                                        ))}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {value.map((item, i) => (
                                        <tr key={i} className="border-b border-border/20 last:border-0">
                                          {columns.map(col => (
                                            <td key={col} className="p-2 font-mono text-muted-foreground">
                                              {String((item as Record<string, unknown>)[col] ?? "")}
                                            </td>
                                          ))}
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                ) : (
                                  <div className="p-2 space-y-1">
                                    {value.map((item, i) => (
                                      <div key={i} className="text-xs font-mono text-muted-foreground py-1 border-b border-border/20 last:border-0">
                                        {String(item)}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          );
                        }

                        // Handle objects
                        if (typeof value === "object" && value !== null) {
                          return (
                            <div key={key} className="border-t border-border/30 pt-2">
                              <div className="text-sm font-medium capitalize mb-1">
                                {key.replace(/_/g, " ")}
                              </div>
                              <div className="bg-background/50 rounded p-2 overflow-auto">
                                <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap break-all">
                                  {JSON.stringify(value, null, 2)}
                                </pre>
                              </div>
                            </div>
                          );
                        }

                        // Handle primitives
                        return (
                          <div key={key} className="grid grid-cols-[auto_1fr] gap-2 text-sm py-1">
                            <span className="text-muted-foreground capitalize">{key.replace(/_/g, " ")}:</span>
                            <span className="font-mono font-medium break-all">
                              {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  </div>
                </details>
              ))}
            </div>
          </ScrollArea>

          <DialogFooter className="border-t pt-4">
            <Button variant="outline" onClick={() => setBatchResultsOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

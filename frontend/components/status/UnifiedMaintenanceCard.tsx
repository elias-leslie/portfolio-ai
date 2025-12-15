"use client";

import { useState, useEffect, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Card } from "@/components/ui/card";
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
  Download,
  Calendar,
  Clock,
  Zap,
  Cpu,
  MemoryStick,
  Camera,
  Users,
  ServerCrash,
  FileX,
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
  type FileCleanupInfo,
  type MaintenanceResult,
  type LastRunSummary,
  type DiskSpaceResponse,
  type DatabaseSizeResponse,
  type MaintenanceScheduleResponse,
  type BackupRequirementCheck,
  type CacheStatusResponse,
} from "@/lib/api/maintenance";
import { toast } from "sonner";

// Unified maintenance item component for consistent display
interface MaintenanceItemProps {
  title: string;
  icon: React.ReactNode;
  metrics: { label: string; value: string }[];
  badge?: { text: string; variant?: "default" | "secondary" | "destructive" | "outline" };
  schedule?: string;
  lastRun?: MaintenanceResult | null;
  onTrigger: () => void;
  isTriggering: boolean;
  disabled?: boolean;
}

function MaintenanceItem({
  title,
  icon,
  metrics,
  badge,
  schedule,
  lastRun,
  onTrigger,
  isTriggering,
  disabled,
}: MaintenanceItemProps) {
  const getStatusIcon = (status?: string) => {
    switch (status) {
      case "success":
        return <CheckCircle2 className="h-3 w-3 text-green-500" />;
      case "error":
        return <AlertCircle className="h-3 w-3 text-red-500" />;
      case "running":
        return <RefreshCw className="h-3 w-3 animate-spin text-blue-500" />;
      default:
        return null;
    }
  };

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium">{title}</span>
          {lastRun?.status && getStatusIcon(lastRun.status)}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={onTrigger}
          disabled={isTriggering || disabled}
          title={`Run ${title} now`}
        >
          {isTriggering ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
        </Button>
      </div>

      <div className="space-y-2 text-sm">
        {metrics.map((metric, idx) => (
          <div key={idx} className="flex justify-between">
            <span className="text-muted-foreground">{metric.label}:</span>
            <span className="font-mono">{metric.value}</span>
          </div>
        ))}
        {badge && (
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Policy:</span>
            <Badge variant={badge.variant || "secondary"} className="text-xs">
              {badge.text}
            </Badge>
          </div>
        )}
        {schedule && (
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Schedule:</span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {schedule}
            </span>
          </div>
        )}
        {lastRun?.started_at && (
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground">Last run:</span>
            <span className="text-xs text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {new Date(lastRun.started_at).toLocaleString()}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

// Section header component
function SectionHeader({ title, icon }: { title: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-3 mt-6 first:mt-0">
      {icon}
      <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">{title}</h3>
    </div>
  );
}

export function UnifiedMaintenanceCard() {
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

  // Dialog state
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string;
    description: string;
    actionLabel: string;
    onConfirm: () => void;
    storageKey?: string;
  } | null>(null);

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

  // State for task results dialog
  const [taskResultOpen, setTaskResultOpen] = useState(false);
  const [taskResult, setTaskResult] = useState<{
    taskName: string;
    dryRun: boolean;
    result: Record<string, unknown> | null;
  } | null>(null);

  // File cleanup trigger handler with dry-run support
  const handleFileCleanupTrigger = async (taskName: string) => {
    setTriggeringTask(taskName);
    try {
      const result = await triggerMaintenanceTask(taskName, {
        dryRun,
        waitForResult: true,
        timeout: 60,
      });

      if (result.result) {
        // Show results dialog for dry-run or completed tasks
        setTaskResult({
          taskName,
          dryRun,
          result: result.result as Record<string, unknown>,
        });
        setTaskResultOpen(true);
      }

      const isDry = dryRun ? " (dry run)" : "";
      if (result.status === "completed") {
        toast.success(`${taskName}${isDry}: ${result.message}`);
      } else if (result.status === "timeout") {
        toast.warning(`${taskName}${isDry}: Still running...`);
      } else {
        toast.success(result.message);
      }

      if (!dryRun) {
        setTimeout(fetchAllData, 2000);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to trigger task";
      toast.error(`Failed to trigger ${taskName}: ${message}`);
    } finally {
      setTriggeringTask(null);
    }
  };

  // Database maintenance handlers with confirmation dialogs
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

  const triggerCleanupNews = () => {
    if (!dryRun && backupCheck && !backupCheck.can_proceed) {
      toast.error(`Cannot run: ${backupCheck.blocking_reason}`);
      return;
    }
    const storageKey = "status.confirm.cleanupNews";
    if (shouldShowDialog(storageKey, !dryRun)) {
      setActionDialogConfig({
        title: "Cleanup Old News",
        description: dryRun
          ? "Preview articles older than 90 days that would be deleted."
          : "⚠️ DESTRUCTIVE: Permanently delete news articles older than 90 days.",
        actionLabel: dryRun ? "Preview" : "Delete",
        onConfirm: handleCleanupNews,
        storageKey: dryRun ? storageKey : undefined,
      });
      setActionDialogOpen(true);
    } else {
      handleCleanupNews();
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

  const triggerVacuumDatabase = () => {
    if (!dryRun && backupCheck && !backupCheck.can_proceed) {
      toast.error(`Cannot run: ${backupCheck.blocking_reason}`);
      return;
    }
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

  const triggerValidateIntegrity = () => {
    if (!dryRun && backupCheck && !backupCheck.can_proceed) {
      toast.error(`Cannot run: ${backupCheck.blocking_reason}`);
      return;
    }
    const storageKey = "status.confirm.validateIntegrity";
    if (shouldShowDialog(storageKey, !dryRun)) {
      setActionDialogConfig({
        title: "Validate Integrity",
        description: dryRun
          ? "Check for orphaned records and consistency issues."
          : "⚠️ Check and attempt to fix integrity issues.",
        actionLabel: dryRun ? "Check" : "Fix",
        onConfirm: handleValidateIntegrity,
        storageKey: dryRun ? storageKey : undefined,
      });
      setActionDialogOpen(true);
    } else {
      handleValidateIntegrity();
    }
  };

  // Run all tasks
  const handleRunAll = async () => {
    toast.info("Running all maintenance tasks...");
    // File cleanup tasks
    const fileCleanupTasks = [
      "cleanup_old_logs_task",
      "cleanup_old_backups_task",
      "cleanup_old_models_task",
      "cleanup_solution_state_task",
    ];
    for (const task of fileCleanupTasks) {
      await handleFileCleanupTrigger(task);
    }
    // Database tasks
    await handleCleanupNews();
    await handleVacuumDatabase();
    await handleValidateIntegrity();
    toast.success("All maintenance tasks completed");
  };

  // Format size helper
  const formatSize = (mb: number) => {
    if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`;
    return `${mb.toFixed(2)} MB`;
  };

  // Summary text - simplified since System Status shows details
  const getSummary = () => {
    if (isLoading) return "Loading...";
    if (diskSpace?.alerts?.length) return `⚠️ ${diskSpace.alerts.length} disk alert(s)`;
    return "Ready";
  };

  const getDiskStatusVariant = (percentage: number): "default" | "secondary" | "destructive" => {
    if (percentage > 85) return "destructive";
    if (percentage > 70) return "secondary";
    return "default";
  };

  const canRunLive = !dryRun && backupCheck?.can_proceed === true;
  const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.can_proceed;

  return (
    <>
      <ExpandableCard
        title="Maintenance"
        description="Unified file cleanup, database maintenance, and system monitoring"
        summary={getSummary()}
        defaultCollapsed
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {/* Dry Run Toggle */}
            <div className="flex items-center gap-2">
              <Switch id="dry-run-unified" checked={dryRun} onCheckedChange={setDryRun} />
              <Label htmlFor="dry-run-unified" className="cursor-pointer text-sm">
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
              disabled={triggeringTask !== null || liveBlocked}
              title="Run all maintenance tasks"
            >
              <PlayCircle className="h-4 w-4 mr-1" />
              Run All
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
          <div className="space-y-2">
            {/* System Status Section - Overview */}
            <SectionHeader title="System Status" icon={<HardDrive className="h-4 w-4 text-muted-foreground" />} />
            <Card className="p-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold">{formatSize(fileCleanup?.total_size_mb || 0)}</div>
                  <div className="text-xs text-muted-foreground">Managed Files</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{formatSize(dbSize?.database_size_mb || 0)}</div>
                  <div className="text-xs text-muted-foreground">Database</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">{formatSize(cacheStatus?.total_size_mb || 0)}</div>
                  <div className="text-xs text-muted-foreground">Dev Caches</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold">
                    {diskSpace?.partitions?.[0]?.used_percentage?.toFixed(0) || "—"}%
                  </div>
                  <div className="text-xs text-muted-foreground">Disk Used</div>
                </div>
              </div>
            </Card>

            {/* File Cleanup Section */}
            <SectionHeader title="File Cleanup" icon={<FolderOpen className="h-4 w-4 text-muted-foreground" />} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <MaintenanceItem
                title="Application Logs"
                icon={<FileText className="h-5 w-5 text-orange-500" />}
                metrics={[
                  { label: "Size", value: formatSize(fileCleanup?.logs?.size_mb || 0) },
                  { label: "Files", value: String(fileCleanup?.logs?.file_count || 0) },
                ]}
                badge={{ text: fileCleanup?.logs?.retention_policy || "N/A" }}
                schedule={fileCleanup?.logs?.schedule}
                onTrigger={() => handleFileCleanupTrigger("cleanup_old_logs_task")}
                isTriggering={triggeringTask === "cleanup_old_logs_task"}
              />
              <MaintenanceItem
                title="Database Backups"
                icon={<Database className="h-5 w-5 text-blue-500" />}
                metrics={[
                  { label: "Size", value: formatSize(fileCleanup?.backups?.size_mb || 0) },
                  { label: "Files", value: String(fileCleanup?.backups?.file_count || 0) },
                ]}
                badge={{ text: fileCleanup?.backups?.retention_policy || "N/A" }}
                schedule={fileCleanup?.backups?.schedule}
                onTrigger={() => handleFileCleanupTrigger("cleanup_old_backups_task")}
                isTriggering={triggeringTask === "cleanup_old_backups_task"}
              />
              <MaintenanceItem
                title="ML Model Versions"
                icon={<Brain className="h-5 w-5 text-purple-500" />}
                metrics={[
                  { label: "Size", value: formatSize(fileCleanup?.models?.size_mb || 0) },
                  { label: "Files", value: String(fileCleanup?.models?.file_count || 0) },
                ]}
                badge={{ text: fileCleanup?.models?.retention_policy || "N/A" }}
                schedule={fileCleanup?.models?.schedule}
                onTrigger={() => handleFileCleanupTrigger("cleanup_old_models_task")}
                isTriggering={triggeringTask === "cleanup_old_models_task"}
              />
              <MaintenanceItem
                title="Test Artifacts"
                icon={<TestTube className="h-5 w-5 text-green-500" />}
                metrics={[
                  { label: "Size", value: formatSize(fileCleanup?.solution_state?.size_mb || 0) },
                  { label: "Files", value: String(fileCleanup?.solution_state?.file_count || 0) },
                ]}
                badge={{ text: fileCleanup?.solution_state?.retention_policy || "N/A" }}
                schedule={fileCleanup?.solution_state?.schedule}
                onTrigger={() => handleFileCleanupTrigger("cleanup_solution_state_task")}
                isTriggering={triggeringTask === "cleanup_solution_state_task"}
              />
            </div>

            {/* Cache Cleanup Section (Optional/Manual) */}
            <SectionHeader title="Cache Cleanup (Optional)" icon={<Zap className="h-4 w-4 text-muted-foreground" />} />
            <Card className="p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className="h-5 w-5 text-yellow-500" />
                    <span className="font-medium">Development Caches</span>
                    <Badge variant="outline" className="text-xs">Manual only</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Python bytecode, linter caches, and build caches. Safe to delete - they regenerate automatically.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleFileCleanupTrigger("cleanup_cache_directories_task")}
                  disabled={triggeringTask === "cleanup_cache_directories_task"}
                  title="Clean all development caches"
                >
                  {triggeringTask === "cleanup_cache_directories_task" ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </div>
              {cacheStatus && cacheStatus.directories.length > 0 && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm font-medium border-b pb-2">
                    <span>Total: {formatSize(cacheStatus.total_size_mb)}</span>
                    <span>{cacheStatus.total_file_count.toLocaleString()} files</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {cacheStatus.directories.filter(d => d.size_mb > 0).map((dir) => (
                      <div key={dir.path} className="text-xs border rounded p-2">
                        <div className="font-medium truncate" title={dir.name}>{dir.name}</div>
                        <div className="flex justify-between text-muted-foreground">
                          <span>{formatSize(dir.size_mb)}</span>
                          <span>{dir.file_count.toLocaleString()} files</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {cacheStatus.directories.every(d => d.size_mb === 0) && (
                    <div className="text-sm text-muted-foreground text-center py-2">
                      All caches are empty
                    </div>
                  )}
                </div>
              )}
            </Card>

            {/* Data Cleanup Section */}
            <SectionHeader title="Data Cleanup" icon={<Trash2 className="h-4 w-4 text-muted-foreground" />} />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MaintenanceItem
                title="Old Agent Runs"
                icon={<Users className="h-5 w-5 text-indigo-500" />}
                metrics={[
                  { label: "Retention", value: "30 days" },
                ]}
                badge={{ text: "Weekly" }}
                schedule="Sunday 04:15 UTC"
                onTrigger={() => handleFileCleanupTrigger("cleanup_old_agent_runs_task")}
                isTriggering={triggeringTask === "cleanup_old_agent_runs_task"}
              />
              <MaintenanceItem
                title="Orphaned Data"
                icon={<ServerCrash className="h-5 w-5 text-red-500" />}
                metrics={[
                  { label: "Type", value: "Integrity fix" },
                ]}
                badge={{ text: "Weekly" }}
                schedule="Sunday 04:30 UTC"
                onTrigger={() => handleFileCleanupTrigger("cleanup_orphaned_data_task")}
                isTriggering={triggeringTask === "cleanup_orphaned_data_task"}
              />
              <MaintenanceItem
                title="Temp Files"
                icon={<FileX className="h-5 w-5 text-gray-500" />}
                metrics={[
                  { label: "Retention", value: "24 hours" },
                ]}
                badge={{ text: "Daily" }}
                schedule="Daily 02:15 UTC"
                onTrigger={() => handleFileCleanupTrigger("cleanup_temp_files_task")}
                isTriggering={triggeringTask === "cleanup_temp_files_task"}
              />
              <MaintenanceItem
                title="Evidence Artifacts"
                icon={<Camera className="h-5 w-5 text-cyan-500" />}
                metrics={[
                  { label: "Keep", value: "5 versions" },
                ]}
                badge={{ text: "Daily" }}
                schedule="Daily 06:00 UTC"
                onTrigger={() => handleFileCleanupTrigger("cleanup_old_versions")}
                isTriggering={triggeringTask === "cleanup_old_versions"}
              />
            </div>

            {/* Database Maintenance Section */}
            <SectionHeader title="Database Maintenance" icon={<Database className="h-4 w-4 text-muted-foreground" />} />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {(() => {
                const cleanupNews = lastRunSummary?.tasks?.cleanup_old_news_task || lastRunSummary?.tasks?.cleanup_news;
                return (
                  <MaintenanceItem
                    title="Cleanup News"
                    icon={<Trash2 className="h-5 w-5 text-orange-500" />}
                    metrics={[
                      {
                        label: "Deleted",
                        value: String((cleanupNews?.summary as Record<string, unknown>)?.deleted || "—"),
                      },
                    ]}
                    badge={{ text: "90 days retention" }}
                    lastRun={cleanupNews || null}
                    onTrigger={triggerCleanupNews}
                    isTriggering={triggeringTask === "cleanup_news"}
                    disabled={liveBlocked}
                  />
                );
              })()}
              {(() => {
                const vacuumDb = lastRunSummary?.tasks?.vacuum_database_task || lastRunSummary?.tasks?.vacuum_database;
                return (
                  <MaintenanceItem
                    title="Vacuum Database"
                    icon={<Database className="h-5 w-5 text-blue-500" />}
                    metrics={[
                      {
                        label: "Reclaimed",
                        value: `${(vacuumDb?.summary as Record<string, unknown>)?.total_reclaimed_mb || "—"} MB`,
                      },
                    ]}
                    badge={{ text: "Weekly" }}
                    lastRun={vacuumDb || null}
                    onTrigger={triggerVacuumDatabase}
                    isTriggering={triggeringTask === "vacuum_database"}
                    disabled={liveBlocked}
                  />
                );
              })()}
              {(() => {
                const validateIntegrity = lastRunSummary?.tasks?.validate_integrity_task || lastRunSummary?.tasks?.validate_integrity;
                return (
                  <MaintenanceItem
                    title="Validate Integrity"
                    icon={<CheckCircle2 className="h-5 w-5 text-green-500" />}
                    metrics={[
                      {
                        label: "Errors",
                        value: String((validateIntegrity?.summary as Record<string, unknown>)?.total_errors || "—"),
                      },
                      {
                        label: "Warnings",
                        value: String((validateIntegrity?.summary as Record<string, unknown>)?.total_warnings || "—"),
                      },
                    ]}
                    badge={{ text: "Daily" }}
                    lastRun={validateIntegrity || null}
                    onTrigger={triggerValidateIntegrity}
                    isTriggering={triggeringTask === "validate_integrity"}
                    disabled={liveBlocked}
                  />
                );
              })()}
            </div>

            {/* Scheduled Tasks Footer */}
            <div className="mt-6 pt-4 border-t">
              <details>
                <summary className="cursor-pointer text-sm font-medium text-muted-foreground hover:text-foreground flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  {schedule?.total_count || 0} Scheduled Tasks
                </summary>
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {schedule &&
                    Object.entries(schedule.scheduled_tasks).map(([name, task]) => (
                      <div key={name} className="text-xs border rounded p-2">
                        <div className="font-medium truncate">{name}</div>
                        <div className="text-muted-foreground">{task.schedule}</div>
                      </div>
                    ))}
                </div>
              </details>
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
                // Skip task_id and internal fields
                if (key === "task_id" || key === "success") return null;
                // Handle details array specially
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
                // Skip empty details arrays
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
    </>
  );
}

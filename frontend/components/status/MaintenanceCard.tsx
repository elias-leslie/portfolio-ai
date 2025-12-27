"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Trash2,
  Database,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  PlayCircle,
  ShieldCheck,
  ShieldAlert,
  Loader2,
} from "lucide-react";
import { ServiceActionDialog } from "./ServiceActionDialog";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import {
  cleanupOldNews,
  vacuumDatabase,
  validateIntegrity,
  getMaintenanceLastRun,
  checkBackupRequirements,
  type MaintenanceResult,
  type LastRunSummary,
  type BackupRequirementCheck,
} from "@/lib/api/maintenance";
import { toast } from "sonner";

interface TaskSectionProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  lastRun: MaintenanceResult | null;
  onTrigger: () => void;
  isLoading: boolean;
}

// Maintenance summary discriminated union types
interface CleanupSummary {
  deleted: number;
  cutoffDate?: string;
}

interface VacuumSummary {
  tables_processed: number;
  tablesProcessed: number;
  totalReclaimedMb: number;
}

interface IntegritySummary {
  checks_run: number;
  checksRun: number;
  totalErrors?: number;
  totalWarnings?: number;
}

type MaintenanceSummary = CleanupSummary | VacuumSummary | IntegritySummary;

function TaskSection({
  title,
  description,
  icon,
  lastRun,
  onTrigger,
  isLoading,
}: TaskSectionProps) {
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "Never run";
    return new Date(dateStr).toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "success":
        return (
          <Badge variant="default" className="flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" />
            Success
          </Badge>
        );
      case "error":
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            Error
          </Badge>
        );
      case "running":
        return (
          <Badge variant="secondary" className="flex items-center gap-1">
            <RefreshCw className="h-3 w-3 animate-spin" />
            Running
          </Badge>
        );
      default:
        return <Badge variant="secondary">Unknown</Badge>;
    }
  };

  const renderSummary = (summary: MaintenanceSummary | null) => {
    if (!summary) return null;

    // Cleanup News summary
    if ("deleted" in summary) {
      return (
        <div className="text-sm space-y-1">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Articles deleted:</span>
            <span className="font-mono">{summary.deleted}</span>
          </div>
          {summary.cutoffDate && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cutoff date:</span>
              <span className="font-mono text-xs">
                {new Date(summary.cutoffDate).toLocaleDateString()}
              </span>
            </div>
          )}
        </div>
      );
    }

    // Vacuum Database summary
    if ("tables_processed" in summary) {
      return (
        <div className="text-sm space-y-1">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Tables processed:</span>
            <span className="font-mono">{summary.tablesProcessed}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Space reclaimed:</span>
            <span className="font-mono">{summary.totalReclaimedMb} MB</span>
          </div>
        </div>
      );
    }

    // Validate Integrity summary
    if ("checks_run" in summary) {
      return (
        <div className="text-sm space-y-1">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Checks run:</span>
            <span className="font-mono">{summary.checksRun}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Errors:</span>
            <span className="font-mono text-red-500">
              {summary.totalErrors || 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Warnings:</span>
            <span className="font-mono text-yellow-500">
              {summary.totalWarnings || 0}
            </span>
          </div>
        </div>
      );
    }

    // Fallback: show JSON
    return (
      <pre className="text-xs bg-muted p-2 rounded overflow-auto max-h-32">
        {JSON.stringify(summary, null, 2)}
      </pre>
    );
  };

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          {icon}
          <div>
            <h3 className="font-semibold">{title}</h3>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        <Button
          size="sm"
          onClick={onTrigger}
          disabled={isLoading}
        >
          {isLoading ? (
            <RefreshCw className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
        </Button>
      </div>

      {lastRun ? (
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Last run:</span>
            {getStatusBadge(lastRun.status)}
          </div>
          <div className="text-sm text-muted-foreground">
            {formatDate(lastRun.startedAt)}
          </div>
          {lastRun.dryRun && (
            <Badge variant="outline" className="text-xs">
              Dry Run
            </Badge>
          )}
          {lastRun.status === "success" && renderSummary(lastRun.summary)}
          {lastRun.status === "error" && lastRun.errorMessage && (
            <div className="text-sm text-red-500 bg-red-50 dark:bg-red-950 p-2 rounded">
              {lastRun.errorMessage}
            </div>
          )}
        </div>
      ) : (
        <div className="pt-2 border-t">
          <span className="text-sm text-muted-foreground">Never run</span>
        </div>
      )}
    </div>
  );
}

export function MaintenanceCard() {
  const [lastRunSummary, setLastRunSummary] = useState<LastRunSummary | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [backupCheck, setBackupCheck] = useState<BackupRequirementCheck | null>(
    null
  );
  const [isCheckingBackup, setIsCheckingBackup] = useState(false);
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string;
    description: string;
    actionLabel: string;
    onConfirm: () => void;
    storageKey?: string;
    isDestructive?: boolean;
  } | null>(null);

  // Fetch last run data on mount
  useEffect(() => {
    fetchLastRunData();
  }, []);

  // Check backup status when dry-run is toggled off
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
      // For maintenance, require backup within 24h and verified
      const check = await checkBackupRequirements(24, true);
      setBackupCheck(check);
      if (!check.canProceed) {
        toast.warning(
          `Backup check: ${check.blockingReason || "Requirements not met"}`,
          { duration: 6000 }
        );
      }
    } catch (error) {
      console.error("Failed to check backup requirements:", error);
      toast.error("Could not verify backup status");
      setBackupCheck({
        backupExists: false,
        backupRecent: false,
        backupVerified: false,
        backupName: null,
        backupAgeHours: null,
        canProceed: false,
        blockingReason: "Could not verify backup status",
        warnings: [],
      });
    } finally {
      setIsCheckingBackup(false);
    }
  };

  const fetchLastRunData = async () => {
    setIsFetching(true);
    try {
      const data = await getMaintenanceLastRun();
      setLastRunSummary(data);
    } catch (error) {
      console.error("Failed to fetch maintenance data:", error);
    } finally {
      setIsFetching(false);
    }
  };

  // Check if user has disabled confirmation dialogs
  // IMPORTANT: For live (non-dry-run) operations, ALWAYS show dialog - no localStorage bypass
  const shouldShowDialog = (storageKey: string, isLiveOperation: boolean) => {
    if (typeof window === "undefined") return true;
    // Live operations always require confirmation - safety first
    if (isLiveOperation) return true;
    return !localStorage.getItem(storageKey);
  };

  const formatTaskSummary = (label: string, result?: MaintenanceResult | null) => {
    if (!result) return `${label}: —`;
    const status = result.status ? result.status.replace(/_/g, " ") : "unknown";
    if (!result.startedAt) return `${label}: ${status}`;
    const timestamp = new Date(result.startedAt).toLocaleTimeString();
    return `${label}: ${status} @ ${timestamp}`;
  };

  const overviewSummary = [
    formatTaskSummary("Cleanup", lastRunSummary?.tasks?.cleanupOldNewsTask || lastRunSummary?.tasks?.cleanupNews),
    formatTaskSummary("Vacuum", lastRunSummary?.tasks?.vacuumDatabaseTask || lastRunSummary?.tasks?.vacuumDatabase),
    formatTaskSummary("Integrity", lastRunSummary?.tasks?.validateIntegrityTask || lastRunSummary?.tasks?.validateIntegrity),
  ].join(" • ");

  // Cleanup News handler
  const handleCleanupNews = async () => {
    setIsLoading(true);
    try {
      const result = await cleanupOldNews(dryRun);
      toast.success(
        `Cleanup ${result.status}: ${result.summary?.deleted || 0} articles ${
          dryRun ? "would be" : ""
        } deleted`,
      );
      await fetchLastRunData();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to cleanup news";
      toast.error(`Cleanup failed: ${message}`);
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerCleanupNews = () => {
    // For live operations, check backup requirements first
    if (!dryRun && backupCheck && !backupCheck.canProceed) {
      toast.error(
        `Cannot run live cleanup: ${backupCheck.blockingReason || "Backup requirements not met"}`,
        { duration: 8000 }
      );
      return;
    }

    const storageKey = "status.confirm.cleanupNews";
    const isLiveOperation = !dryRun;

    if (shouldShowDialog(storageKey, isLiveOperation)) {
      setActionDialogConfig({
        title: "Cleanup Old News",
        description: dryRun
          ? "This will preview articles that would be deleted (older than 90 days). No actual deletion will occur."
          : "⚠️ DESTRUCTIVE: This will permanently delete news articles older than 90 days. This action cannot be undone. Backup verified: ✓",
        actionLabel: dryRun ? "Preview Cleanup" : "Delete Articles",
        onConfirm: handleCleanupNews,
        // Only allow "don't ask again" for dry-run operations
        storageKey: dryRun ? storageKey : undefined,
        isDestructive: !dryRun,
      });
      setActionDialogOpen(true);
    } else {
      handleCleanupNews().catch(() => {});
    }
  };

  // Vacuum Database handler
  const handleVacuumDatabase = async () => {
    setIsLoading(true);
    try {
      const result = await vacuumDatabase(dryRun);
      toast.success(
        `Vacuum ${result.status}: ${
          result.summary?.totalReclaimedMb || 0
        } MB ${dryRun ? "could be" : ""} reclaimed`,
      );
      await fetchLastRunData();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to vacuum database";
      toast.error(`Vacuum failed: ${message}`);
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerVacuumDatabase = () => {
    // Vacuum is generally safe, but still check backup for live mode
    if (!dryRun && backupCheck && !backupCheck.canProceed) {
      toast.error(
        `Cannot run live vacuum: ${backupCheck.blockingReason || "Backup requirements not met"}`,
        { duration: 8000 }
      );
      return;
    }

    const storageKey = "status.confirm.vacuumDatabase";
    const isLiveOperation = !dryRun;

    if (shouldShowDialog(storageKey, isLiveOperation)) {
      setActionDialogConfig({
        title: "Vacuum Database",
        description: dryRun
          ? "This will analyze database tables and show potential space savings without making changes."
          : "This will optimize all database tables using VACUUM ANALYZE. This is a safe operation but may take a few minutes. Backup verified: ✓",
        actionLabel: dryRun ? "Analyze Tables" : "Vacuum Database",
        onConfirm: handleVacuumDatabase,
        // Only allow "don't ask again" for dry-run operations
        storageKey: dryRun ? storageKey : undefined,
        isDestructive: !dryRun,
      });
      setActionDialogOpen(true);
    } else {
      handleVacuumDatabase().catch(() => {});
    }
  };

  // Validate Integrity handler
  const handleValidateIntegrity = async () => {
    setIsLoading(true);
    try {
      const result = await validateIntegrity(dryRun);
      const summary = result.summary as Record<string, unknown> | null;
      const totalErrors = typeof summary?.totalErrors === 'number' ? summary.totalErrors : 0;
      const totalWarnings = typeof summary?.totalWarnings === 'number' ? summary.totalWarnings : 0;
      const totalInfo = typeof summary?.totalInfo === 'number' ? summary.totalInfo : 0;
      const totalIssues = totalErrors + totalWarnings + totalInfo;
      toast.success(
        `Validation ${result.status}: ${totalIssues} issues found (${totalErrors} errors, ${totalWarnings} warnings)`,
      );
      await fetchLastRunData();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to validate integrity";
      toast.error(`Validation failed: ${message}`);
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const triggerValidateIntegrity = () => {
    // For fix mode, require backup
    if (!dryRun && backupCheck && !backupCheck.canProceed) {
      toast.error(
        `Cannot run live fix: ${backupCheck.blockingReason || "Backup requirements not met"}`,
        { duration: 8000 }
      );
      return;
    }

    const storageKey = "status.confirm.validateIntegrity";
    const isLiveOperation = !dryRun;

    if (shouldShowDialog(storageKey, isLiveOperation)) {
      setActionDialogConfig({
        title: "Validate Data Integrity",
        description: dryRun
          ? "This will check for orphaned records, missing relationships, and data consistency issues without making changes."
          : "⚠️ DESTRUCTIVE: This will check for integrity issues and attempt to fix them automatically. Use with caution. Backup verified: ✓",
        actionLabel: dryRun ? "Check Integrity" : "Fix Issues",
        onConfirm: handleValidateIntegrity,
        // Only allow "don't ask again" for dry-run operations
        storageKey: dryRun ? storageKey : undefined,
        isDestructive: !dryRun,
      });
      setActionDialogOpen(true);
    } else {
      handleValidateIntegrity().catch(() => {});
    }
  };

  return (
    <>
      <ExpandableCard
        title="Database Maintenance"
        description="Cleanup, optimize, and validate database integrity."
        summary={overviewSummary}
        defaultCollapsed
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <Switch id="dry-run" checked={dryRun} onCheckedChange={setDryRun} />
              <Label htmlFor="dry-run" className="cursor-pointer">
                Dry Run
              </Label>
            </div>
            {/* Backup status indicator - only shown when dry-run is OFF */}
            {!dryRun && (
              <div className="flex items-center gap-1.5">
                {isCheckingBackup ? (
                  <Badge variant="secondary" className="flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Checking backup...
                  </Badge>
                ) : backupCheck?.canProceed ? (
                  <Badge variant="default" className="flex items-center gap-1 bg-green-600">
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
            <Button
              variant="outline"
              size="sm"
              onClick={fetchLastRunData}
              disabled={isFetching}
              title="Refresh last run summary"
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          <TaskSection
            title="Cleanup Old News"
            description="Remove news articles older than 90 days"
            icon={<Trash2 className="h-5 w-5 text-orange-500" />}
            lastRun={lastRunSummary?.tasks?.cleanupOldNewsTask || lastRunSummary?.tasks?.cleanupNews || null}
            onTrigger={triggerCleanupNews}
            isLoading={isLoading}
          />

          <TaskSection
            title="Vacuum Database"
            description="Optimize tables and reclaim disk space"
            icon={<Database className="h-5 w-5 text-blue-500" />}
            lastRun={lastRunSummary?.tasks?.vacuumDatabaseTask || lastRunSummary?.tasks?.vacuumDatabase || null}
            onTrigger={triggerVacuumDatabase}
            isLoading={isLoading}
          />

          <TaskSection
            title="Validate Data Integrity"
            description="Check for orphaned records and consistency issues"
            icon={<CheckCircle2 className="h-5 w-5 text-green-500" />}
            lastRun={lastRunSummary?.tasks?.validateIntegrityTask || lastRunSummary?.tasks?.validateIntegrity || null}
            onTrigger={triggerValidateIntegrity}
            isLoading={isLoading}
          />
        </div>
      </ExpandableCard>

      {/* Service Action Dialog */}
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
    </>
  );
}

"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
} from "lucide-react";
import { ServiceActionDialog } from "./ServiceActionDialog";
import {
  cleanupOldNews,
  vacuumDatabase,
  validateIntegrity,
  getMaintenanceLastRun,
  type MaintenanceResult,
  type LastRunSummary,
} from "@/lib/api/maintenance";

interface TaskSectionProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  lastRun: MaintenanceResult | null;
  onTrigger: () => void;
  isLoading: boolean;
}

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

  const renderSummary = (summary: Record<string, any> | null) => {
    if (!summary) return null;

    // Cleanup News summary
    if ("deleted" in summary) {
      return (
        <div className="text-sm space-y-1">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Articles deleted:</span>
            <span className="font-mono">{summary.deleted}</span>
          </div>
          {summary.cutoff_date && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Cutoff date:</span>
              <span className="font-mono text-xs">
                {new Date(summary.cutoff_date).toLocaleDateString()}
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
            <span className="font-mono">{summary.tables_processed}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Space reclaimed:</span>
            <span className="font-mono">{summary.total_reclaimed_mb} MB</span>
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
            <span className="font-mono">{summary.checks_run}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Errors:</span>
            <span className="font-mono text-red-500">
              {summary.total_errors || 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Warnings:</span>
            <span className="font-mono text-yellow-500">
              {summary.total_warnings || 0}
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
            {formatDate(lastRun.started_at)}
          </div>
          {lastRun.dry_run && (
            <Badge variant="outline" className="text-xs">
              Dry Run
            </Badge>
          )}
          {lastRun.status === "success" && renderSummary(lastRun.summary)}
          {lastRun.status === "error" && lastRun.error_message && (
            <div className="text-sm text-red-500 bg-red-50 dark:bg-red-950 p-2 rounded">
              {lastRun.error_message}
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
  const [actionDialogOpen, setActionDialogOpen] = useState(false);
  const [actionDialogConfig, setActionDialogConfig] = useState<{
    title: string;
    description: string;
    actionLabel: string;
    onConfirm: () => void;
    storageKey?: string;
  } | null>(null);

  // Fetch last run data on mount
  useEffect(() => {
    fetchLastRunData();
  }, []);

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
  const shouldShowDialog = (storageKey: string) => {
    if (typeof window === "undefined") return true;
    return !localStorage.getItem(storageKey);
  };

  // Cleanup News handler
  const handleCleanupNews = async () => {
    setIsLoading(true);
    try {
      const result = await cleanupOldNews(dryRun);
      alert(
        `Cleanup ${result.status}: ${result.summary?.deleted || 0} articles ${dryRun ? "would be" : ""} deleted`
      );
      await fetchLastRunData();
    } catch (error) {
      alert(
        `Error: ${error instanceof Error ? error.message : "Failed to cleanup news"}`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const triggerCleanupNews = () => {
    const storageKey = "status.confirm.cleanupNews";
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: "Cleanup Old News",
        description: dryRun
          ? "This will preview articles that would be deleted (older than 90 days). No actual deletion will occur."
          : "This will permanently delete news articles older than 90 days. This action cannot be undone.",
        actionLabel: dryRun ? "Preview Cleanup" : "Delete Articles",
        onConfirm: handleCleanupNews,
        storageKey,
      });
      setActionDialogOpen(true);
    } else {
      handleCleanupNews();
    }
  };

  // Vacuum Database handler
  const handleVacuumDatabase = async () => {
    setIsLoading(true);
    try {
      const result = await vacuumDatabase(dryRun);
      alert(
        `Vacuum ${result.status}: ${result.summary?.total_reclaimed_mb || 0} MB ${dryRun ? "could be" : ""} reclaimed`
      );
      await fetchLastRunData();
    } catch (error) {
      alert(
        `Error: ${error instanceof Error ? error.message : "Failed to vacuum database"}`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const triggerVacuumDatabase = () => {
    const storageKey = "status.confirm.vacuumDatabase";
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: "Vacuum Database",
        description: dryRun
          ? "This will analyze database tables and show potential space savings without making changes."
          : "This will optimize all database tables using VACUUM ANALYZE. This is a safe operation but may take a few minutes.",
        actionLabel: dryRun ? "Analyze Tables" : "Vacuum Database",
        onConfirm: handleVacuumDatabase,
        storageKey,
      });
      setActionDialogOpen(true);
    } else {
      handleVacuumDatabase();
    }
  };

  // Validate Integrity handler
  const handleValidateIntegrity = async () => {
    setIsLoading(true);
    try {
      const result = await validateIntegrity(dryRun);
      const summary = result.summary;
      const totalIssues =
        (summary?.total_errors || 0) +
        (summary?.total_warnings || 0) +
        (summary?.total_info || 0);
      alert(
        `Validation ${result.status}: ${totalIssues} issues found (${summary?.total_errors || 0} errors, ${summary?.total_warnings || 0} warnings)`
      );
      await fetchLastRunData();
    } catch (error) {
      alert(
        `Error: ${error instanceof Error ? error.message : "Failed to validate integrity"}`
      );
    } finally {
      setIsLoading(false);
    }
  };

  const triggerValidateIntegrity = () => {
    const storageKey = "status.confirm.validateIntegrity";
    if (shouldShowDialog(storageKey)) {
      setActionDialogConfig({
        title: "Validate Data Integrity",
        description: dryRun
          ? "This will check for orphaned records, missing relationships, and data consistency issues without making changes."
          : "This will check for integrity issues and attempt to fix them automatically. Use with caution.",
        actionLabel: dryRun ? "Check Integrity" : "Fix Issues",
        onConfirm: handleValidateIntegrity,
        storageKey,
      });
      setActionDialogOpen(true);
    } else {
      handleValidateIntegrity();
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Database Maintenance</CardTitle>
              <p className="text-sm text-muted-foreground">
                Cleanup, optimize, and validate database integrity
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  id="dry-run"
                  checked={dryRun}
                  onCheckedChange={setDryRun}
                />
                <Label htmlFor="dry-run" className="cursor-pointer">
                  Dry Run
                </Label>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchLastRunData}
                disabled={isFetching}
              >
                <RefreshCw
                  className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
                />
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <TaskSection
            title="Cleanup Old News"
            description="Remove news articles older than 90 days"
            icon={<Trash2 className="h-5 w-5 text-orange-500" />}
            lastRun={lastRunSummary?.cleanup_news || null}
            onTrigger={triggerCleanupNews}
            isLoading={isLoading}
          />

          <TaskSection
            title="Vacuum Database"
            description="Optimize tables and reclaim disk space"
            icon={<Database className="h-5 w-5 text-blue-500" />}
            lastRun={lastRunSummary?.vacuum_database || null}
            onTrigger={triggerVacuumDatabase}
            isLoading={isLoading}
          />

          <TaskSection
            title="Validate Data Integrity"
            description="Check for orphaned records and consistency issues"
            icon={<CheckCircle2 className="h-5 w-5 text-green-500" />}
            lastRun={lastRunSummary?.validate_integrity || null}
            onTrigger={triggerValidateIntegrity}
            isLoading={isLoading}
          />
        </CardContent>
      </Card>

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

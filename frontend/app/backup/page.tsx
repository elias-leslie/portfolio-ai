"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  HardDrive,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
  Terminal,
} from "lucide-react";
import { toast } from "sonner";

import { PageContainer, PageHeader } from "@/components/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  backupKeys,
  getBackupStatus,
  getBackupHistory,
  triggerBackup,
  getBackupJobStatus,
  formatBytes,
  formatBackupAge,
  getStatusColor,
  type BackupStatusResponse,
  type BackupEntry,
  type BackupJobStatus,
} from "@/lib/api/backup";

function StatusIcon({ status }: { status: BackupStatusResponse["status"] }) {
  switch (status) {
    case "healthy":
      return <CheckCircle2 className="size-5 text-gain" />;
    case "stale":
      return <Clock className="size-5 text-warning" />;
    case "no_backups":
    case "error":
      return <AlertCircle className="size-5 text-loss" />;
    default:
      return <HardDrive className="size-5 text-text-muted" />;
  }
}

function BackupStatusCard() {
  const { data: status, isLoading, error } = useQuery({
    queryKey: backupKeys.status(),
    queryFn: getBackupStatus,
    staleTime: 30_000, // 30 seconds
    refetchInterval: 60_000, // 1 minute
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="size-5" />
            Backup Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-text-muted" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <HardDrive className="size-5" />
            Backup Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-loss bg-loss/10 p-4 text-sm text-loss">
            Failed to load backup status: {error?.message || "Unknown error"}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <StatusIcon status={status.status} />
          Backup Status
          <Badge
            variant={
              status.status === "healthy"
                ? "success"
                : status.status === "stale"
                  ? "warning"
                  : "destructive"
            }
            className="ml-auto"
          >
            {status.status.toUpperCase()}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className={cn("text-sm", getStatusColor(status.status))}>
          {status.message}
        </p>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-text-muted">Total Backups:</span>{" "}
            <span className="font-medium">{status.backup_count}</span>
          </div>
          <div>
            <span className="text-text-muted">Destination:</span>{" "}
            <span className="font-mono text-xs">{status.destination}</span>
          </div>
        </div>

        {status.latest_backup && (
          <div className="rounded-md bg-surface-muted p-3">
            <div className="text-xs text-text-muted uppercase mb-1">Latest Backup</div>
            <div className="font-mono text-sm">{status.latest_backup.name}</div>
            <div className="flex gap-4 mt-1 text-xs text-text-muted">
              <span>{formatBackupAge(status.latest_backup.timestamp)}</span>
              <span>{formatBytes(status.latest_backup.size_bytes)}</span>
              <span>DB: {formatBytes(status.latest_backup.db_size_bytes)}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TriggerBackupCard() {
  const queryClient = useQueryClient();
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [showOutput, setShowOutput] = useState(false);

  const triggerMutation = useMutation({
    mutationFn: (quick: boolean) => triggerBackup(quick),
    onSuccess: (data) => {
      if (data.status === "started") {
        setActiveJobId(data.job_id);
        toast.success("Backup started", { description: data.message });
      } else {
        toast.info("Backup already running", { description: data.message });
        setActiveJobId(data.job_id);
      }
    },
    onError: (error) => {
      toast.error("Failed to trigger backup", {
        description: error instanceof Error ? error.message : "Unknown error",
      });
    },
  });

  // Poll job status when we have an active job
  const { data: jobStatus } = useQuery({
    queryKey: backupKeys.job(activeJobId || ""),
    queryFn: () => getBackupJobStatus(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const data = query.state.data as BackupJobStatus | undefined;
      // Stop polling when job is complete
      if (data?.status === "completed" || data?.status === "failed") {
        return false;
      }
      return 2000; // Poll every 2 seconds while running
    },
  });

  // Handle job completion
  useEffect(() => {
    if (jobStatus?.status === "completed") {
      toast.success("Backup completed successfully!");
      queryClient.invalidateQueries({ queryKey: backupKeys.status() });
      queryClient.invalidateQueries({ queryKey: backupKeys.history() });
    } else if (jobStatus?.status === "failed") {
      toast.error("Backup failed", {
        description: jobStatus.error || "Unknown error",
      });
    }
  }, [jobStatus?.status, queryClient, jobStatus?.error]);

  const isRunning = triggerMutation.isPending || jobStatus?.status === "running";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <RefreshCw className={cn("size-5", isRunning && "animate-spin")} />
          Trigger Backup
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button
            onClick={() => triggerMutation.mutate(false)}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Running...
              </>
            ) : (
              <>
                <HardDrive className="mr-2 size-4" />
                Full Backup
              </>
            )}
          </Button>
          <Button
            variant="outline"
            onClick={() => triggerMutation.mutate(true)}
            disabled={isRunning}
          >
            Quick Backup
          </Button>
        </div>

        <p className="text-xs text-text-muted">
          <strong>Full Backup:</strong> Creates fresh PostgreSQL dump + archives all project data.
          <br />
          <strong>Quick Backup:</strong> Uses existing daily DB dump (faster, for checkpoints).
        </p>

        {jobStatus && activeJobId && (
          <div className="rounded-md border border-border bg-surface-muted p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge
                  variant={
                    jobStatus.status === "completed"
                      ? "success"
                      : jobStatus.status === "failed"
                        ? "destructive"
                        : "secondary"
                  }
                >
                  {jobStatus.status.toUpperCase()}
                </Badge>
                <span className="text-xs text-text-muted font-mono">
                  Job: {activeJobId}
                </span>
              </div>
              {jobStatus.output && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowOutput(!showOutput)}
                >
                  {showOutput ? (
                    <ChevronDown className="size-4" />
                  ) : (
                    <ChevronRight className="size-4" />
                  )}
                  <Terminal className="ml-1 size-4" />
                </Button>
              )}
            </div>

            {showOutput && jobStatus.output && (
              <pre className="max-h-48 overflow-auto rounded bg-bg p-2 text-xs font-mono">
                {jobStatus.output}
              </pre>
            )}

            {jobStatus.error && (
              <div className="text-xs text-loss">{jobStatus.error}</div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BackupHistoryCard() {
  const { data: history, isLoading } = useQuery({
    queryKey: backupKeys.history(),
    queryFn: getBackupHistory,
    staleTime: 60_000, // 1 minute
  });

  const [expandedBackup, setExpandedBackup] = useState<string | null>(null);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Backup History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-text-muted" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const backups = history?.backups || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Backup History</span>
          <span className="text-sm font-normal text-text-muted">
            {backups.length} / {history?.retention || 30} max
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {backups.length === 0 ? (
          <div className="py-8 text-center text-text-muted">
            No backups yet. Click &quot;Full Backup&quot; to create your first backup.
          </div>
        ) : (
          <div className="space-y-2">
            {backups.slice(0, 10).map((backup: BackupEntry, index: number) => (
              <div
                key={backup.name}
                className={cn(
                  "rounded-md border border-border p-3 transition-colors",
                  expandedBackup === backup.name && "bg-surface-muted"
                )}
              >
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() =>
                    setExpandedBackup(
                      expandedBackup === backup.name ? null : backup.name
                    )
                  }
                >
                  <div className="flex items-center gap-2">
                    {expandedBackup === backup.name ? (
                      <ChevronDown className="size-4 text-text-muted" />
                    ) : (
                      <ChevronRight className="size-4 text-text-muted" />
                    )}
                    <span className="font-mono text-sm">{backup.name}</span>
                    {index === 0 && (
                      <Badge variant="success" className="text-xs">
                        Latest
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-text-muted">
                    <span>{formatBackupAge(backup.timestamp)}</span>
                    <span>{formatBytes(backup.size_bytes)}</span>
                  </div>
                </div>

                {expandedBackup === backup.name && (
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs border-t border-border pt-3">
                    <div>
                      <span className="text-text-muted">Timestamp:</span>{" "}
                      <span className="font-mono">
                        {new Date(backup.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div>
                      <span className="text-text-muted">Archive Size:</span>{" "}
                      <span>{formatBytes(backup.size_bytes)}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">DB Size:</span>{" "}
                      <span>{formatBytes(backup.db_size_bytes)}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Status:</span>{" "}
                      <Badge
                        variant={backup.status === "ok" ? "success" : "destructive"}
                        className="text-xs"
                      >
                        {backup.status}
                      </Badge>
                    </div>
                  </div>
                )}
              </div>
            ))}

            {backups.length > 10 && (
              <div className="pt-2 text-center text-xs text-text-muted">
                Showing 10 of {backups.length} backups
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RestoreInfoCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Restore Information</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-text-muted">
          To restore from a backup, use the command line:
        </p>

        <div className="rounded-md bg-surface-muted p-3 font-mono text-xs space-y-2">
          <div className="text-text-muted"># List available backups</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh --list</div>

          <div className="text-text-muted mt-3"># Restore latest backup</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh --latest</div>

          <div className="text-text-muted mt-3"># Restore specific backup</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh portfolio-ai-YYYYMMDD-HHMMSS.tar.gz</div>

          <div className="text-text-muted mt-3"># Database only</div>
          <div>bash ~/portfolio-ai/scripts/restore.sh --db-only --latest</div>
        </div>

        <div className="rounded-md border border-warning bg-warning/10 p-3 text-sm text-warning">
          <strong>Warning:</strong> Restore operations will overwrite existing data.
          Make sure you have a current backup before restoring.
        </div>
      </CardContent>
    </Card>
  );
}

export default function BackupPage() {
  return (
    <PageContainer className="py-6">
      <PageHeader
        title="Backup Management"
        description="Manage project backups stored on Davion-Sidar"
      />

      <div className="grid gap-6 mt-6 lg:grid-cols-2">
        <BackupStatusCard />
        <TriggerBackupCard />
        <BackupHistoryCard />
        <RestoreInfoCard />
      </div>
    </PageContainer>
  );
}

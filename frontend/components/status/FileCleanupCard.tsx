"use client";

import { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
} from "lucide-react";
import { ExpandableCard } from "@/components/status/ExpandableCard";
import {
  getFileCleanupStatus,
  triggerMaintenanceTask,
  type FileCleanupStatusResponse,
  type FileCleanupInfo,
} from "@/lib/api/maintenance";
import { toast } from "sonner";

interface CleanupCategoryProps {
  title: string;
  icon: React.ReactNode;
  info: FileCleanupInfo | null;
  taskName: string;
  onTrigger: (taskName: string) => void;
  isTriggering: boolean;
  triggeringTask: string | null;
}

function CleanupCategory({
  title,
  icon,
  info,
  taskName,
  onTrigger,
  isTriggering,
  triggeringTask,
}: CleanupCategoryProps) {
  if (!info) {
    return (
      <div className="border rounded-lg p-4 opacity-50">
        <div className="flex items-center gap-2 mb-2">
          {icon}
          <span className="font-medium">{title}</span>
        </div>
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  const isThisTaskTriggering = isTriggering && triggeringTask === taskName;

  return (
    <div className="border rounded-lg p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium">{title}</span>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onTrigger(taskName)}
          disabled={isTriggering}
          title={`Run ${title} cleanup now`}
        >
          {isThisTaskTriggering ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <PlayCircle className="h-4 w-4" />
          )}
        </Button>
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-muted-foreground">Size:</span>
          <span className="font-mono">
            {info.sizeMb >= 1024
              ? `${(info.sizeMb / 1024).toFixed(2)} GB`
              : `${info.sizeMb.toFixed(2)} MB`}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Files:</span>
          <span className="font-mono">{info.fileCount}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-muted-foreground">Retention:</span>
          <Badge variant="secondary" className="text-xs">
            {info.retentionPolicy}
          </Badge>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-muted-foreground">Schedule:</span>
          <span className="text-xs text-muted-foreground">{info.schedule}</span>
        </div>
      </div>
    </div>
  );
}

export function FileCleanupCard() {
  const [status, setStatus] = useState<FileCleanupStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isTriggering, setIsTriggering] = useState(false);
  const [triggeringTask, setTriggeringTask] = useState<string | null>(null);
  const [lastTriggerResult, setLastTriggerResult] = useState<{
    success: boolean;
    taskName: string;
  } | null>(null);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const data = await getFileCleanupStatus();
      setStatus(data);
    } catch (error) {
      console.error("Failed to fetch file cleanup status:", error);
      toast.error("Failed to load file cleanup status");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleTrigger = async (taskName: string) => {
    setIsTriggering(true);
    setTriggeringTask(taskName);
    try {
      const result = await triggerMaintenanceTask(taskName);
      toast.success(`${result.message}`);
      setLastTriggerResult({ success: true, taskName });
      // Refresh status after a short delay to show updated sizes
      setTimeout(fetchStatus, 2000);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to trigger task";
      toast.error(`Failed to trigger ${taskName}: ${message}`);
      setLastTriggerResult({ success: false, taskName });
    } finally {
      setIsTriggering(false);
      setTriggeringTask(null);
    }
  };

  const formatTotalSize = () => {
    if (!status) return "Loading...";
    const sizeMb = status.totalSizeMb;
    if (sizeMb >= 1024) {
      return `${(sizeMb / 1024).toFixed(2)} GB total`;
    }
    return `${sizeMb.toFixed(2)} MB total`;
  };

  return (
    <ExpandableCard
      title="File Cleanup"
      description="Manage automated cleanup of logs, backups, and artifacts"
      summary={formatTotalSize()}
      defaultCollapsed
      actions={
        <div className="flex items-center gap-2">
          {lastTriggerResult && (
            <Badge
              variant={lastTriggerResult.success ? "default" : "destructive"}
              className="flex items-center gap-1"
            >
              {lastTriggerResult.success ? (
                <CheckCircle2 className="h-3 w-3" />
              ) : (
                <AlertCircle className="h-3 w-3" />
              )}
              {lastTriggerResult.taskName.replace(/_/g, " ")}
            </Badge>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={fetchStatus}
            disabled={isLoading}
            title="Refresh file cleanup status"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      }
    >
      {isLoading && !status ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <CleanupCategory
            title="Application Logs"
            icon={<FileText className="h-5 w-5 text-warning" />}
            info={status?.logs ?? null}
            taskName="cleanup_old_logs_task"
            onTrigger={handleTrigger}
            isTriggering={isTriggering}
            triggeringTask={triggeringTask}
          />

          <CleanupCategory
            title="Database Backups"
            icon={<Database className="h-5 w-5 text-accent" />}
            info={status?.backups ?? null}
            taskName="cleanup_old_backups_task"
            onTrigger={handleTrigger}
            isTriggering={isTriggering}
            triggeringTask={triggeringTask}
          />

          <CleanupCategory
            title="ML Model Versions"
            icon={<Brain className="h-5 w-5 text-accent" />}
            info={status?.models ?? null}
            taskName="cleanup_old_models_task"
            onTrigger={handleTrigger}
            isTriggering={isTriggering}
            triggeringTask={triggeringTask}
          />

          <CleanupCategory
            title="Test Artifacts"
            icon={<TestTube className="h-5 w-5 text-gain" />}
            info={status?.solutionState ?? null}
            taskName="cleanup_solution_state_task"
            onTrigger={handleTrigger}
            isTriggering={isTriggering}
            triggeringTask={triggeringTask}
          />
        </div>
      )}

      <div className="mt-4 pt-4 border-t text-sm text-muted-foreground">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-4 w-4" />
          <span>
            Automated cleanup runs on schedule. Click play to run immediately.
          </span>
        </div>
      </div>
    </ExpandableCard>
  );
}

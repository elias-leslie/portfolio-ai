"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  RefreshCw,
  PlayCircle,
  Loader2,
  ShieldCheck,
  ShieldAlert,
} from "lucide-react";

interface BackupCheckResult {
  canProceed: boolean;
  blockingReason?: string | null;
}

interface MaintenanceTableToolbarProps {
  dryRun: boolean;
  setDryRun: (value: boolean) => void;
  isCheckingBackup: boolean;
  backupCheck: BackupCheckResult | null;
  isRunningAll: boolean;
  isRefreshing: boolean;
  filteredTaskCount: number;
  currentTaskIndex: number;
  onRunAll: () => void;
  onRefresh: () => void;
}

export function MaintenanceTableToolbar({
  dryRun,
  setDryRun,
  isCheckingBackup,
  backupCheck,
  isRunningAll,
  isRefreshing,
  filteredTaskCount,
  currentTaskIndex,
  onRunAll,
  onRefresh,
}: MaintenanceTableToolbarProps) {
  const canRunLive = !dryRun && backupCheck?.canProceed === true;
  const liveBlocked = !dryRun && backupCheck !== null && !backupCheck.canProceed;

  return (
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
        onClick={onRunAll}
        disabled={isRunningAll || liveBlocked}
        title={dryRun ? "Preview all tasks (dry run)" : "Execute all tasks"}
      >
        {isRunningAll ? (
          <>
            <Loader2 className="h-4 w-4 mr-1 animate-spin" />
            Running {currentTaskIndex + 1}/{filteredTaskCount}...
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
        onClick={onRefresh}
        disabled={isRefreshing}
        title="Refresh all data"
      >
        <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
      </Button>
    </div>
  );
}

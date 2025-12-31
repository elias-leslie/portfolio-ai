"use client";

import React from "react";
import { formatSize } from "@/lib/maintenance/formatters";

interface MaintenanceSummaryStatsProps {
  filesSizeMb: number;
  databaseSizeMb: number;
  cacheSizeMb: number;
  diskUsedPercentage: number | null;
}

export function MaintenanceSummaryStats({
  filesSizeMb,
  databaseSizeMb,
  cacheSizeMb,
  diskUsedPercentage,
}: MaintenanceSummaryStatsProps) {
  return (
    <div className="grid grid-cols-4 gap-4 p-4 bg-surface-muted/30 rounded-lg">
      <div className="text-center">
        <div className="text-xl font-bold">{formatSize(filesSizeMb)}</div>
        <div className="text-xs text-muted-foreground">Managed Files</div>
      </div>
      <div className="text-center">
        <div className="text-xl font-bold">{formatSize(databaseSizeMb)}</div>
        <div className="text-xs text-muted-foreground">Database</div>
      </div>
      <div className="text-center">
        <div className="text-xl font-bold">{formatSize(cacheSizeMb)}</div>
        <div className="text-xs text-muted-foreground">Dev Caches</div>
      </div>
      <div className="text-center">
        <div className="text-xl font-bold">
          {diskUsedPercentage !== null ? `${diskUsedPercentage.toFixed(0)}%` : "—"}
        </div>
        <div className="text-xs text-muted-foreground">Disk Used</div>
      </div>
    </div>
  );
}

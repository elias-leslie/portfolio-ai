import React from 'react';
import { CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { MaintenanceResult } from '@/lib/api/maintenance';

export type TaskCategory = 'file' | 'cache' | 'data' | 'database' | 'system';

/**
 * Format size in MB to human-readable string
 */
export function formatSize(mb: number | null): string {
  if (mb === null) return "—";
  if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
  return `${mb.toFixed(1)} MB`;
}

/**
 * Format last run time as relative string
 */
export function formatLastRun(lastRun: MaintenanceResult | null): string {
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
}

/**
 * Get status icon based on last run result
 */
export function getStatusIcon(lastRun: MaintenanceResult | null): React.ReactNode {
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
}

const CATEGORY_COLORS: Record<TaskCategory, string> = {
  file: "bg-status-warning/20 text-status-warning",
  cache: "bg-status-warning/20 text-status-warning",
  data: "bg-status-info/20 text-status-info",
  database: "bg-accent/20 text-accent",
  system: "bg-surface-muted text-text-muted",
};

const CATEGORY_LABELS: Record<TaskCategory, string> = {
  file: "File",
  cache: "Cache",
  data: "Data",
  database: "DB",
  system: "System",
};

/**
 * Get category badge component
 */
export function getCategoryBadge(category: TaskCategory): React.ReactNode {
  return (
    <Badge variant="outline" className={`text-xs ${CATEGORY_COLORS[category]}`}>
      {CATEGORY_LABELS[category]}
    </Badge>
  );
}

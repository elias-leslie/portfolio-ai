/**
 * Maintenance task configuration - extracted to reduce MaintenanceTable complexity
 */

import React from "react";
import {
  cleanupOldNews,
  vacuumDatabase,
  validateIntegrity,
  type MaintenanceResult,
} from "@/lib/api/maintenance";
import {
  FileText,
  Database,
  Brain,
  TestTube,
  Zap,
  Users,
  ServerCrash,
  FileX,
  Camera,
  Trash2,
  CheckCircle2,
  RotateCcw,
} from "lucide-react";

// Task category types
export type TaskCategory = "file" | "cache" | "data" | "database" | "system";

// Static task configuration (without runtime data)
export interface TaskConfig {
  id: string;
  name: string;
  category: TaskCategory;
  iconName: keyof typeof TASK_ICONS;
  iconColor: string;
  taskName: string; // Celery task name
  description: string;
  schedule: string;
  retentionPolicy: string | null;
  isDbTask?: boolean;
  supportsDryRun?: boolean;
  // Data source mapping for file cleanup tasks
  fileCleanupKey?: "logs" | "backups" | "models" | "solutionState";
  // For tasks with fallback lastRun lookups
  fallbackTaskName?: string;
}

// Icon map for serialization
export const TASK_ICONS = {
  FileText,
  Database,
  Brain,
  TestTube,
  Zap,
  Users,
  ServerCrash,
  FileX,
  Camera,
  Trash2,
  CheckCircle2,
  RotateCcw,
} as const;

// Icon color mappings by task type
export const ICON_COLORS = {
  warning: "text-status-warning",
  info: "text-status-info",
  accent: "text-accent",
  success: "text-status-success",
  error: "text-status-error",
  muted: "text-text-muted",
} as const;

/**
 * Static task configurations - defines all maintenance tasks
 * Runtime data (sizeMb, fileCount, lastRun) added during task building
 */
export const TASK_CONFIGS: TaskConfig[] = [
  // File cleanup tasks
  {
    id: "logs",
    name: "Application Logs",
    category: "file",
    iconName: "FileText",
    iconColor: ICON_COLORS.warning,
    taskName: "cleanup_old_logs_task",
    description: "Application log files",
    schedule: "Weekly Sun 04:00",
    retentionPolicy: "7 days",
    supportsDryRun: true,
    fileCleanupKey: "logs",
  },
  {
    id: "backups",
    name: "Database Backups",
    category: "file",
    iconName: "Database",
    iconColor: ICON_COLORS.info,
    taskName: "cleanup_old_backups_task",
    description: "PostgreSQL backup files",
    schedule: "Weekly Sun 04:05",
    retentionPolicy: "Keep 7",
    supportsDryRun: true,
    fileCleanupKey: "backups",
  },
  {
    id: "models",
    name: "ML Model Versions",
    category: "file",
    iconName: "Brain",
    iconColor: ICON_COLORS.accent,
    taskName: "cleanup_old_models_task",
    description: "Trained ML model files",
    schedule: "Weekly Sun 04:10",
    retentionPolicy: "Keep 3",
    supportsDryRun: true,
    fileCleanupKey: "models",
  },
  {
    id: "solution_state",
    name: "Test Artifacts",
    category: "file",
    iconName: "TestTube",
    iconColor: ICON_COLORS.success,
    taskName: "cleanup_solution_state_task",
    description: "UI regression test artifacts",
    schedule: "Weekly Sun 04:20",
    retentionPolicy: "Keep 5",
    supportsDryRun: true,
    fileCleanupKey: "solutionState",
  },

  // Cache cleanup (manual only)
  {
    id: "dev_caches",
    name: "Dev Caches",
    category: "cache",
    iconName: "Zap",
    iconColor: ICON_COLORS.warning,
    taskName: "cleanup_cache_directories_task",
    description: "Python bytecode, linter caches, build caches",
    schedule: "Manual",
    retentionPolicy: "Auto-regenerate",
    supportsDryRun: true,
  },

  // Data cleanup tasks
  {
    id: "agent_runs",
    name: "Old Agent Runs",
    category: "data",
    iconName: "Users",
    iconColor: ICON_COLORS.accent,
    taskName: "cleanup_old_agent_runs_task",
    description: "Historical agent execution records",
    schedule: "Weekly Sun 04:15",
    retentionPolicy: "30 days",
    supportsDryRun: true,
  },
  {
    id: "orphaned_data",
    name: "Orphaned Data",
    category: "data",
    iconName: "ServerCrash",
    iconColor: ICON_COLORS.error,
    taskName: "cleanup_orphaned_data_task",
    description: "Records without valid foreign keys",
    schedule: "Weekly Sun 04:30",
    retentionPolicy: "Integrity fix",
    supportsDryRun: true,
  },
  {
    id: "temp_files",
    name: "Temp Files",
    category: "data",
    iconName: "FileX",
    iconColor: ICON_COLORS.muted,
    taskName: "cleanup_temp_files_task",
    description: "Temporary processing files",
    schedule: "Daily 02:15",
    retentionPolicy: "24 hours",
    supportsDryRun: true,
  },
  {
    id: "evidence",
    name: "Evidence Artifacts",
    category: "data",
    iconName: "Camera",
    iconColor: ICON_COLORS.info,
    taskName: "cleanup_old_versions",
    description: "Feature verification screenshots",
    schedule: "Daily 06:00",
    retentionPolicy: "5 versions",
    supportsDryRun: true,
  },
  {
    id: "debug_captures",
    name: "Debug Captures",
    category: "data",
    iconName: "Camera",
    iconColor: ICON_COLORS.muted,
    taskName: "cleanup_debug_captures",
    description: "Debug screenshots and traces",
    schedule: "Daily 06:00",
    retentionPolicy: "7 days",
    supportsDryRun: true,
  },

  // Database maintenance tasks
  {
    id: "cleanup_news",
    name: "Old News",
    category: "database",
    iconName: "Trash2",
    iconColor: ICON_COLORS.warning,
    taskName: "cleanup_old_news_task",
    description: "Delete news articles older than 90 days",
    schedule: "Daily 03:00",
    retentionPolicy: "90 days",
    isDbTask: true,
    supportsDryRun: true,
    fallbackTaskName: "cleanup_news",
  },
  {
    id: "vacuum_db",
    name: "Vacuum Database",
    category: "database",
    iconName: "Database",
    iconColor: ICON_COLORS.info,
    taskName: "vacuum_database_task",
    description: "Reclaim space and update statistics",
    schedule: "Weekly Sun 05:30",
    retentionPolicy: null,
    isDbTask: true,
    supportsDryRun: true,
    fallbackTaskName: "vacuum_database",
  },
  {
    id: "validate_integrity",
    name: "Validate Integrity",
    category: "database",
    iconName: "CheckCircle2",
    iconColor: ICON_COLORS.success,
    taskName: "validate_integrity_task",
    description: "Check for orphaned records and consistency",
    schedule: "Daily 04:00",
    retentionPolicy: null,
    isDbTask: true,
    supportsDryRun: true,
    fallbackTaskName: "validate_integrity",
  },

  // System tasks
  {
    id: "rotate_logs",
    name: "Rotate Logs",
    category: "system",
    iconName: "RotateCcw",
    iconColor: ICON_COLORS.muted,
    taskName: "rotate_logs_task",
    description: "Archive and compress old log files",
    schedule: "Daily 01:00",
    retentionPolicy: null,
    supportsDryRun: true,
  },
];

/**
 * Get icon element for a task config
 */
export function getTaskIcon(config: TaskConfig): React.ReactNode {
  const IconComponent = TASK_ICONS[config.iconName];
  return React.createElement(IconComponent, {
    className: `h-4 w-4 ${config.iconColor}`,
  });
}

/**
 * Database task dialog configuration
 * Used for confirmation dialogs before running DB tasks
 */
export interface DbTaskDialogConfig {
  title: string;
  dryRunDescription: string;
  liveDescription: string;
  dryRunLabel: string;
  liveLabel: string;
  storageKey: string;
  successExtractor: (result: DbTaskResult) => string;
}

export interface DbTaskResult {
  status: string;
  summary?: Record<string, unknown> | null;
}

/**
 * Configuration for database task dialogs and result formatting
 */
export const DB_TASK_DIALOG_CONFIGS: Record<string, DbTaskDialogConfig> = {
  cleanup_news: {
    title: "Cleanup Old News",
    dryRunDescription: "Preview articles older than 90 days that would be deleted.",
    liveDescription: "Permanently delete news articles older than 90 days.",
    dryRunLabel: "Preview",
    liveLabel: "Delete",
    storageKey: "status.confirm.cleanupNews",
    successExtractor: (result) => {
      const summary = result.summary as Record<string, unknown> | null;
      const deleted = (summary?.deleted as number) || 0;
      return `${deleted} articles`;
    },
  },
  vacuum_db: {
    title: "Vacuum Database",
    dryRunDescription: "Analyze tables and show potential space savings.",
    liveDescription: "Optimize all database tables using VACUUM ANALYZE.",
    dryRunLabel: "Analyze",
    liveLabel: "Vacuum",
    storageKey: "status.confirm.vacuumDatabase",
    successExtractor: (result) => {
      const summary = result.summary as Record<string, unknown> | null;
      const reclaimed = (summary?.totalReclaimedMb as number) || 0;
      return `${reclaimed} MB`;
    },
  },
  validate_integrity: {
    title: "Validate Integrity",
    dryRunDescription: "Check for orphaned records and consistency issues.",
    liveDescription: "Check and attempt to fix integrity issues.",
    dryRunLabel: "Check",
    liveLabel: "Fix",
    storageKey: "status.confirm.validateIntegrity",
    successExtractor: (result) => {
      const summary = result.summary as Record<string, unknown> | null;
      const errors = (summary?.totalErrors as number) || 0;
      const warnings = (summary?.totalWarnings as number) || 0;
      return `${errors} errors, ${warnings} warnings`;
    },
  },
};

/**
 * Map of database task IDs to their API functions
 * Used by MaintenanceTable to invoke database maintenance tasks
 */
export const DB_TASK_API_FUNCTIONS: Record<
  string,
  (dryRun: boolean) => Promise<MaintenanceResult>
> = {
  cleanup_news: cleanupOldNews,
  vacuum_db: vacuumDatabase,
  validate_integrity: validateIntegrity,
};

/**
 * API client for maintenance endpoints.
 *
 * Provides functions to trigger and monitor database maintenance tasks:
 * - Cleanup old news articles
 * - Vacuum database tables
 * - Validate data integrity
 * - Monitor maintenance schedule and resources
 */

import { get, post } from "./client";

// Types

export interface MaintenanceResult {
  task_id: number;
  task_name: string;
  status: "running" | "success" | "error";
  started_at: string;
  completed_at: string | null;
  dry_run: boolean;
  summary: Record<string, unknown> | null;
  error_message: string | null;
}

export interface LastRunSummary {
  /** Dynamic dict of task_name -> last run result (supports all tasks) */
  tasks: Record<string, MaintenanceResult | null>;
}

export interface MaintenanceHistory {
  runs: MaintenanceResult[];
  total: number;
}

export interface ScheduledTask {
  task: string;
  schedule: string;
  args?: unknown[];
}

export interface MaintenanceScheduleResponse {
  scheduled_tasks: Record<string, ScheduledTask>;
  total_count: number;
}

export interface PartitionInfo {
  path: string;
  name: string;
  total_bytes: number;
  used_bytes: number;
  free_bytes: number;
  used_percentage: number;
}

export interface DiskSpaceResponse {
  task_id: string;
  partitions: PartitionInfo[];
  alerts: Array<{
    partition: string;
    used_percentage: number;
    free_mb: number;
  }>;
  alert_count: number;
  duration_seconds: number;
  success: boolean;
}

export interface TableSize {
  table: string;
  size_bytes: number;
  size_pretty: string;
}

export interface DatabaseSizeResponse {
  task_id: string;
  database_size_bytes: number;
  database_size_mb: number;
  top_tables: TableSize[];
  duration_seconds: number;
  success: boolean;
}

export interface MaintenanceStatsResponse {
  metric_name?: string;
  days?: number;
  data_points?: number;
  trends?: Array<{
    recorded_at: string;
    value: number;
    unit: string | null;
    metadata: Record<string, unknown> | null;
  }>;
  summary?: Record<
    string,
    {
      value: number;
      unit: string | null;
      recorded_at: string;
    }
  >;
  metric_count?: number;
}

export interface TriggerTaskResponse {
  task_id: string;
  task_name: string;
  status: "triggered" | "completed" | "timeout";
  message: string;
  result?: Record<string, unknown> | null;
}

export interface BackupRequirementCheck {
  backup_exists: boolean;
  backup_recent: boolean;
  backup_verified: boolean;
  backup_name: string | null;
  backup_age_hours: number | null;
  can_proceed: boolean;
  blocking_reason: string | null;
  warnings: string[];
}

export interface FileCleanupInfo {
  path: string;
  size_mb: number;
  file_count: number;
  retention_policy: string;
  schedule: string;
}

export interface FileCleanupStatusResponse {
  logs: FileCleanupInfo;
  backups: FileCleanupInfo;
  models: FileCleanupInfo;
  solution_state: FileCleanupInfo;
  total_size_mb: number;
}

export interface CacheDirectoryInfo {
  name: string;
  path: string;
  size_mb: number;
  file_count: number;
  description: string;
}

export interface CacheStatusResponse {
  directories: CacheDirectoryInfo[];
  total_size_mb: number;
  total_file_count: number;
}

// API Functions

/**
 * Check if backup requirements are met for maintenance operations.
 *
 * @param maxAgeHours - Maximum age of backup in hours (default: 24)
 * @param requireVerification - Whether backup must be verified (default: true)
 * @returns Backup requirement check result
 */
export async function checkBackupRequirements(
  maxAgeHours: number = 24,
  requireVerification: boolean = true
): Promise<BackupRequirementCheck> {
  const params = new URLSearchParams({
    max_age_hours: maxAgeHours.toString(),
    require_verification: requireVerification.toString(),
  });
  return get<BackupRequirementCheck>(
    `/api/backup/check-requirements?${params.toString()}`
  );
}

/**
 * Get maintenance schedule for all tasks.
 *
 * @returns Schedule information for all maintenance tasks
 */
export async function getMaintenanceSchedule(): Promise<MaintenanceScheduleResponse> {
  return get<MaintenanceScheduleResponse>("/api/maintenance/schedule");
}

/**
 * Get disk space usage information.
 *
 * @returns Disk space details for all mounted filesystems
 */
export async function getMaintenanceDiskSpace(): Promise<DiskSpaceResponse> {
  return get<DiskSpaceResponse>("/api/maintenance/disk-space");
}

/**
 * Get database size and table breakdown.
 *
 * @returns Database size information with per-table breakdown
 */
export async function getMaintenanceDatabaseSize(): Promise<DatabaseSizeResponse> {
  return get<DatabaseSizeResponse>("/api/maintenance/database-size");
}

/**
 * Get maintenance statistics.
 *
 * @param metricName - Specific metric to fetch (optional)
 * @param days - Number of days of historical data (optional)
 * @returns Maintenance statistics data
 */
export async function getMaintenanceStats(
  metricName?: string,
  days?: number
): Promise<MaintenanceStatsResponse> {
  const params = new URLSearchParams();

  if (metricName) {
    params.append("metric_name", metricName);
  }

  if (days !== undefined) {
    params.append("days", days.toString());
  }

  const url = params.toString()
    ? `/api/maintenance/stats?${params.toString()}`
    : "/api/maintenance/stats";

  return get<MaintenanceStatsResponse>(url);
}

/**
 * Trigger a maintenance task by name.
 *
 * @param taskName - The name of the maintenance task to trigger
 * @param options - Optional trigger options
 * @param options.dryRun - Preview changes without executing
 * @param options.waitForResult - Wait for task completion and return result
 * @param options.timeout - Max seconds to wait (default: 30)
 * @returns Task trigger response with status, ID, and optionally result
 */
export async function triggerMaintenanceTask(
  taskName: string,
  options?: { dryRun?: boolean; waitForResult?: boolean; timeout?: number }
): Promise<TriggerTaskResponse> {
  const params = new URLSearchParams();
  if (options?.dryRun) params.append("dry_run", "true");
  if (options?.waitForResult) params.append("wait_for_result", "true");
  if (options?.timeout) params.append("timeout", options.timeout.toString());

  const url = params.toString()
    ? `/api/maintenance/trigger/${taskName}?${params.toString()}`
    : `/api/maintenance/trigger/${taskName}`;

  return post<TriggerTaskResponse>(url, {});
}

/**
 * Trigger cleanup of old news articles.
 *
 * @param dryRun - Preview mode without actual deletion
 * @param days - Delete news older than N days (default: 90)
 * @returns Maintenance result with execution details
 */
export async function cleanupOldNews(
  dryRun: boolean = true,
  days: number = 90
): Promise<MaintenanceResult> {
  return post<MaintenanceResult>("/api/maintenance/cleanup-news", {
    dry_run: dryRun,
    days,
  });
}

/**
 * Trigger database vacuum operation.
 *
 * @param dryRun - Preview mode without actual vacuum
 * @param tables - Specific tables to vacuum (undefined = all tables)
 * @returns Maintenance result with execution details
 */
export async function vacuumDatabase(
  dryRun: boolean = false,
  tables?: string[]
): Promise<MaintenanceResult> {
  return post<MaintenanceResult>("/api/maintenance/vacuum-database", {
    dry_run: dryRun,
    tables: tables || null,
  });
}

/**
 * Trigger data integrity validation.
 *
 * @param dryRun - Report-only mode without fixes
 * @returns Maintenance result with execution details
 */
export async function validateIntegrity(
  dryRun: boolean = true
): Promise<MaintenanceResult> {
  return post<MaintenanceResult>("/api/maintenance/validate-integrity", {
    dry_run: dryRun,
  });
}

/**
 * Get last run details for each maintenance task.
 *
 * @returns Last run summary for all tasks
 */
export async function getMaintenanceLastRun(): Promise<LastRunSummary> {
  return get<LastRunSummary>("/api/maintenance/last-run");
}

/**
 * Get maintenance execution history.
 *
 * @param taskName - Filter by task name (optional)
 * @param limit - Maximum number of results (default: 50, max: 200)
 * @returns Maintenance history with list of runs
 */
export async function getMaintenanceHistory(
  taskName?: string,
  limit: number = 50
): Promise<MaintenanceHistory> {
  const params = new URLSearchParams();

  if (taskName) {
    params.append("task_name", taskName);
  }

  params.append("limit", limit.toString());

  return get<MaintenanceHistory>(`/api/maintenance/history?${params.toString()}`);
}

/**
 * Get file cleanup status for all cleanup directories.
 *
 * @returns File cleanup status with sizes and retention policies
 */
export async function getFileCleanupStatus(): Promise<FileCleanupStatusResponse> {
  return get<FileCleanupStatusResponse>("/api/maintenance/file-cleanup-status");
}

/**
 * Get cache directory status for optional cleanup.
 *
 * These caches regenerate automatically and are safe to delete.
 *
 * @returns Cache directory sizes and info
 */
export async function getCacheStatus(): Promise<CacheStatusResponse> {
  return get<CacheStatusResponse>("/api/maintenance/cache-status");
}

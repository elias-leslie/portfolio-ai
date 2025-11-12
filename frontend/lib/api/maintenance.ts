/**
 * API client for maintenance endpoints.
 *
 * Provides functions to trigger and monitor database maintenance tasks:
 * - Cleanup old news articles
 * - Vacuum database tables
 * - Validate data integrity
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://192.168.8.233:8000";

// Types

export interface MaintenanceResult {
  task_id: number;
  task_name: string;
  status: "running" | "success" | "error";
  started_at: string;
  completed_at: string | null;
  dry_run: boolean;
  summary: Record<string, any> | null;
  error_message: string | null;
}

export interface LastRunSummary {
  cleanup_news: MaintenanceResult | null;
  vacuum_database: MaintenanceResult | null;
  validate_integrity: MaintenanceResult | null;
}

export interface MaintenanceHistory {
  runs: MaintenanceResult[];
  total: number;
}

// API Functions

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
  const response = await fetch(`${API_BASE_URL}/api/maintenance/cleanup-news`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dry_run: dryRun,
      days,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to cleanup news: ${error}`);
  }

  return response.json();
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
  const response = await fetch(`${API_BASE_URL}/api/maintenance/vacuum-database`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dry_run: dryRun,
      tables: tables || null,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to vacuum database: ${error}`);
  }

  return response.json();
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
  const response = await fetch(`${API_BASE_URL}/api/maintenance/validate-integrity`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      dry_run: dryRun,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to validate integrity: ${error}`);
  }

  return response.json();
}

/**
 * Get last run details for each maintenance task.
 *
 * @returns Last run summary for all tasks
 */
export async function getMaintenanceLastRun(): Promise<LastRunSummary> {
  const response = await fetch(`${API_BASE_URL}/api/maintenance/last-run`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to fetch last run data: ${error}`);
  }

  return response.json();
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

  const response = await fetch(
    `${API_BASE_URL}/api/maintenance/history?${params.toString()}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to fetch maintenance history: ${error}`);
  }

  return response.json();
}

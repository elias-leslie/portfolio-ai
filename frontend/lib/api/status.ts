/**
 * API client for system status and service monitoring
 */

import { get } from "./client";

/**
 * Service status from process monitoring
 */
export interface ServiceStatus {
  service_name: string;
  status: "running" | "down" | "degraded";
  pid?: number;
  uptime_seconds?: number;
  memory_mb?: number;
  message: string;
}

/**
 * Health check response
 */
export interface HealthResponse {
  status: "healthy" | "degraded" | "down";
  timestamp: string;
  version: string;
  uptime_seconds: number;
  checks: Record<string, CheckResult>;
  sources: Record<string, SourceHealthCheck>;
  services: Record<string, ServiceStatus>;
  cache_stats?: CacheStats;
  agent_stats?: AgentStats;
  watchlist_stats?: WatchlistStats;
  api_quotas?: APIQuotaInfo[];
  workflow_health?: WorkflowHealthInfo;
}

export interface CheckResult {
  status: "ok" | "degraded" | "down";
  latency_ms?: number;
  last_success?: string;
  message?: string;
}

export interface SourceHealthCheck {
  status: "ok" | "degraded" | "down";
  last_success?: string;
  success_rate?: number;
  avg_latency_ms?: number;
  rate_limit_hits: number;
  in_cooldown: boolean;
  cooldown_remaining_seconds: number;
}

export interface CacheStats {
  total_cached: number;
  cache_age_minutes?: number;
}

export interface AgentStats {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  avg_duration_s?: number;
  avg_cost_usd?: number;
}

export interface WatchlistStats {
  total_items: number;
  last_refresh?: string;
  refresh_age_minutes?: number;
  items_with_scores: number;
}

export interface APIQuotaInfo {
  source_name: string;
  configured: boolean;
  rate_limit?: string;
  daily_limit?: string;
  estimated_capacity?: number;
}

export interface DayBarFreshnessInfo {
  symbol: string;
  last_updated?: string;
  age_days?: number;
}

export interface TableFreshnessStatus {
  table_name: string;
  last_updated: string | null;
  age_hours: number | null;
  status: "fresh" | "stale" | "critical" | "unknown" | "error";
  row_count: number | null;
  expected_refresh_hours: number;
  description: string;
}

export interface TableFreshnessResponse {
  tables: TableFreshnessStatus[];
  fresh_count: number;
  stale_count: number;
  critical_count: number;
  timestamp: string;
}

export interface CeleryWorkerStatus {
  active: boolean;
  pool_size?: number;
  active_tasks?: number;
  message: string;
}

export interface APIKeyStatusInfo {
  source: string;
  configured: boolean;
  env_var: string;
}

export interface DiskUsageInfo {
  total_gb: number;
  used_gb: number;
  free_gb: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
}

export interface WorkflowHealthInfo {
  status: "healthy" | "warning" | "critical";
  total_workflows_24h: number;
  successful_workflows: number;
  failed_workflows: number;
  blocked_workflows: number;
  success_rate: number;
  avg_duration_s?: number;
  last_successful_workflow?: string;
  last_successful_type?: string;
  failures_by_type: Record<string, number>;
  blocked_by_type: Record<string, number>;
}

export interface WorkflowMetrics {
  recent_workflows: Array<{
    id: number;
    type: string;
    status: string;
    created_at: string | null;
  }>;
  summary_by_type: Record<string, Record<string, number>>;
  total_by_status: Record<string, number>;
  total_workflows_7d: number;
  success_rate: number;
}

/**
 * Detailed health check response with additional system information
 */
export interface DetailedHealthResponse extends HealthResponse {
  day_bars_freshness?: DayBarFreshnessInfo[];
  celery_worker?: CeleryWorkerStatus;
  api_keys?: APIKeyStatusInfo[];
  disk_usage?: DiskUsageInfo;
  workflow_metrics?: WorkflowMetrics;
}

/**
 * Log response
 */
export interface LogResponse {
  service: string;
  log_file: string;
  lines: string[];
  total_lines: number;
  timestamp: string;
}

/**
 * Fetch system status including all services
 */
export async function fetchSystemStatus(): Promise<HealthResponse> {
  return get<HealthResponse>("/health");
}

/**
 * Fetch detailed system status with additional checks
 */
export async function fetchDetailedHealth(): Promise<DetailedHealthResponse> {
  return get<DetailedHealthResponse>("/health/detailed");
}

/**
 * Fetch logs for a specific service
 */
export async function fetchServiceLogs(
  service: string,
  lines: number = 100
): Promise<LogResponse> {
  return get<LogResponse>(`/api/status/logs/${service}?lines=${lines}`);
}

/**
 * Fetch table freshness status for all monitored tables
 */
export async function fetchTableFreshness(): Promise<TableFreshnessResponse> {
  return get<TableFreshnessResponse>("/api/status/table-freshness");
}

// System Resources Types
export interface ResourceUsage {
  total_gb: number;
  used_gb: number;
  free_gb?: number;
  available_gb?: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
}

export interface CpuUsage {
  percent_used: number;
  cores: number;
  status: "ok" | "warning" | "critical";
}

export interface DatabasePoolUsage {
  pool_size: number;
  checked_out: number;
  overflow: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
}

export interface SystemResourcesResponse {
  disk: ResourceUsage;
  memory: ResourceUsage;
  cpu: CpuUsage;
  database_pool: DatabasePoolUsage;
  timestamp: string;
}

/**
 * Fetch system resource usage (CPU, memory, disk, database pool)
 */
export async function fetchSystemResources(): Promise<SystemResourcesResponse> {
  return get<SystemResourcesResponse>("/api/status/resources");
}

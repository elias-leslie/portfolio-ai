/**
 * API client for system status and service monitoring
 */

import { get } from "./client";

/**
 * Service status from process monitoring
 */
export interface ServiceStatus {
  serviceName: string;
  status: "running" | "down" | "degraded";
  pid?: number;
  uptimeSeconds?: number;
  memoryMb?: number;
  message: string;
}

/**
 * Health check response
 */
export interface HealthResponse {
  status: "healthy" | "degraded" | "down";
  timestamp: string;
  version: string;
  uptimeSeconds: number;
  checks: Record<string, CheckResult>;
  sources: Record<string, SourceHealthCheck>;
  services: Record<string, ServiceStatus>;
  cacheStats?: CacheStats;
  agentStats?: AgentStats;
  watchlistStats?: WatchlistStats;
  apiQuotas?: APIQuotaInfo[];
  workflowHealth?: WorkflowHealthInfo;
}

export interface CheckResult {
  status: "ok" | "degraded" | "down";
  latencyMs?: number;
  lastSuccess?: string;
  message?: string;
}

export interface SourceHealthCheck {
  status: "ok" | "degraded" | "down";
  lastSuccess?: string;
  successRate?: number;
  avgLatencyMs?: number;
  rateLimitHits: number;
  inCooldown: boolean;
  cooldownRemainingSeconds: number;
}

export interface CacheStats {
  totalCached: number;
  cacheAgeMinutes?: number;
}

export interface AgentStats {
  totalRuns: number;
  completedRuns: number;
  failedRuns: number;
  avgDurationS?: number;
  avgCostUsd?: number;
}

export interface WatchlistStats {
  totalItems: number;
  lastRefresh?: string;
  refreshAgeMinutes?: number;
  itemsWithScores: number;
}

export interface APIQuotaInfo {
  sourceName: string;
  configured: boolean;
  rateLimit?: string;
  dailyLimit?: string;
  estimatedCapacity?: number;
}

export interface DayBarFreshnessInfo {
  symbol: string;
  lastUpdated?: string;
  ageDays?: number;
}

export interface TableFreshnessStatus {
  tableName: string;
  lastUpdated: string | null;
  ageHours: number | null;
  status: "fresh" | "stale" | "critical" | "unknown" | "error";
  rowCount: number | null;
  expectedRefreshHours: number;
  description: string;
}

export interface TableFreshnessResponse {
  tables: TableFreshnessStatus[];
  freshCount: number;
  staleCount: number;
  criticalCount: number;
  timestamp: string;
}

export interface CeleryWorkerStatus {
  active: boolean;
  poolSize?: number;
  activeTasks?: number;
  message: string;
}

export interface APIKeyStatusInfo {
  source: string;
  configured: boolean;
  envVar: string;
}

export interface DiskUsageInfo {
  totalGb: number;
  usedGb: number;
  freeGb: number;
  percentUsed: number;
  status: "ok" | "warning" | "critical";
}

export interface WorkflowHealthInfo {
  status: "healthy" | "warning" | "critical";
  totalWorkflows24H: number;
  successfulWorkflows: number;
  failedWorkflows: number;
  blockedWorkflows: number;
  successRate: number;
  avgDurationS?: number;
  lastSuccessfulWorkflow?: string;
  lastSuccessfulType?: string;
  failuresByType: Record<string, number>;
  blockedByType: Record<string, number>;
}

export interface WorkflowMetrics {
  recentWorkflows: Array<{
    id: number;
    type: string;
    status: string;
    createdAt: string | null;
  }>;
  summaryByType: Record<string, Record<string, number>>;
  totalByStatus: Record<string, number>;
  totalWorkflows7D: number;
  successRate: number;
}

/**
 * Detailed health check response with additional system information
 */
export interface DetailedHealthResponse extends HealthResponse {
  dayBarsFreshness?: DayBarFreshnessInfo[];
  celeryWorker?: CeleryWorkerStatus;
  apiKeys?: APIKeyStatusInfo[];
  diskUsage?: DiskUsageInfo;
  workflowMetrics?: WorkflowMetrics;
}

/**
 * Log response
 */
export interface LogResponse {
  service: string;
  logFile: string;
  lines: string[];
  totalLines: number;
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
  totalGb: number;
  usedGb: number;
  freeGb?: number;
  availableGb?: number;
  percentUsed: number;
  status: "ok" | "warning" | "critical";
}

export interface CpuUsage {
  percentUsed: number;
  cores: number;
  status: "ok" | "warning" | "critical";
}

export interface DatabasePoolUsage {
  poolSize: number;
  checkedOut: number;
  overflow: number;
  percentUsed: number;
  status: "ok" | "warning" | "critical";
}

export interface SystemResourcesResponse {
  disk: ResourceUsage;
  memory: ResourceUsage;
  cpu: CpuUsage;
  databasePool: DatabasePoolUsage;
  timestamp: string;
}

/**
 * Fetch system resource usage (CPU, memory, disk, database pool)
 */
export async function fetchSystemResources(): Promise<SystemResourcesResponse> {
  return get<SystemResourcesResponse>("/api/status/resources");
}

/**
 * Unified log entry from all services
 */
export interface UnifiedLogEntry {
  timestamp: string;
  service: string;
  level: "CRITICAL" | "ERROR" | "WARN" | "INFO" | "DEBUG" | "UNKNOWN";
  message: string;
}

/**
 * Unified logs response
 */
export interface UnifiedLogsResponse {
  logs: UnifiedLogEntry[];
  totalEntries: number;
  levelCounts: Record<string, number>;
  timestamp: string;
}

/**
 * Log level configuration
 */
export interface LogLevelConfig {
  currentLevel: string;
  availableLevels: string[];
}

/**
 * Fetch unified logs from all services
 */
export async function fetchUnifiedLogs(params: {
  lines?: number;
  since?: string;
  level?: string;
  service?: string;
}): Promise<UnifiedLogsResponse> {
  const searchParams = new URLSearchParams();
  if (params.lines) searchParams.append("lines", params.lines.toString());
  if (params.since) searchParams.append("since", params.since);
  if (params.level) searchParams.append("level", params.level);
  if (params.service) searchParams.append("service", params.service);
  return get<UnifiedLogsResponse>(`/api/status/unified-logs?${searchParams}`);
}

/**
 * Fetch current log level configuration
 */
export async function fetchLogLevelConfig(): Promise<LogLevelConfig> {
  return get<LogLevelConfig>("/api/status/log-level");
}

/**
 * Set log level for all services
 */
export async function setLogLevel(level: string): Promise<void> {
  const response = await fetch("/api/status/log-level", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ level }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to change log level");
  }
}

/**
 * Restart all services
 */
export async function restartAllServices(): Promise<void> {
  const response = await fetch("/api/status/restart-services", {
    method: "POST",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Failed to restart services");
  }
}

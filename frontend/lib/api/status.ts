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

/**
 * Log response
 */
export interface LogResponse {
  service: string;
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
 * Fetch logs for a specific service
 */
export async function fetchServiceLogs(
  service: string,
  lines: number = 100
): Promise<LogResponse> {
  return get<LogResponse>(`/api/status/logs/${service}?lines=${lines}`);
}

/**
 * Sitemap API Client
 *
 * Endpoints:
 * - GET /api/sitemap/entries - List entries
 * - GET /api/sitemap/entries/{id} - Get entry detail
 * - POST /api/sitemap/discover - Trigger discovery
 * - POST /api/sitemap/check/{id} - Check entry health
 * - POST /api/sitemap/check-all - Check all entries
 * - GET /api/sitemap/health-summary - Aggregate stats
 * - POST /api/sitemap/register - Register manual entry
 * - DELETE /api/sitemap/entries/{id} - Delete entry
 * - GET /api/sitemap/history-stats - History stats for maintenance
 * - POST /api/sitemap/cleanup-history - Trigger cleanup
 */

import { get, post, del } from "./client";

// ============================================================================
// Types
// ============================================================================

export type EntryType = "frontend_page" | "api_endpoint" | "manual";
export type HealthStatus = "healthy" | "warning" | "error" | "unknown";

export interface SitemapEntry {
  id: number;
  port: number;
  path: string;
  method: string;
  entry_type: EntryType;
  source: string | null;
  title: string | null;
  parent_path: string | null;
  health_status: HealthStatus;
  console_errors: number;
  console_warnings: number;
  http_status: number | null;
  response_time_ms: number | null;
  last_error_message: string | null;
  artifact_id: number | null;
  last_checked_at: string | null;
  discovered_at: string | null;
}

export interface SitemapListResponse {
  total: number;
  entries: SitemapEntry[];
}

export interface HealthSummaryResponse {
  total: number;
  healthy: number;
  warning: number;
  error: number;
  unknown: number;
  by_port: Record<string, { healthy: number; warning: number; error: number; unknown: number }>;
}

export interface SitemapFilters {
  port?: number;
  health_status?: HealthStatus;
  entry_type?: EntryType;
  limit?: number;
  offset?: number;
}

export interface DiscoveryResponse {
  openapi_discovered: number;
  frontend_discovered: number;
  websocket_discovered: number;
  nextjs_discovered: number;
  api_imported: number;
  total_saved: number;
}

export interface HealthCheckResponse {
  success: boolean;
  entry_id?: number;
  health_status?: HealthStatus;
  console_errors?: number;
  console_warnings?: number;
  http_status?: number;
  response_time_ms?: number;
  error?: string;
}

export interface HistoryStatsResponse {
  total_rows: number;
  oldest_entry: string | null;
  storage_size: string;
}

export interface CleanupResponse {
  deleted: number;
  retention_days: number;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch sitemap entries with optional filters
 */
export async function fetchSitemapEntries(
  filters: SitemapFilters = {}
): Promise<SitemapListResponse> {
  const params = new URLSearchParams();
  if (filters.port) params.append("port", filters.port.toString());
  if (filters.health_status) params.append("health_status", filters.health_status);
  if (filters.entry_type) params.append("entry_type", filters.entry_type);
  if (filters.limit) params.append("limit", filters.limit.toString());
  if (filters.offset) params.append("offset", filters.offset.toString());

  const queryString = params.toString();
  return get<SitemapListResponse>(
    `/api/sitemap/entries${queryString ? `?${queryString}` : ""}`
  );
}

/**
 * Fetch a single sitemap entry by ID
 */
export async function fetchSitemapEntry(id: number): Promise<SitemapEntry> {
  return get<SitemapEntry>(`/api/sitemap/entries/${id}`);
}

/**
 * Fetch aggregate health summary
 */
export async function fetchHealthSummary(): Promise<HealthSummaryResponse> {
  return get<HealthSummaryResponse>("/api/sitemap/health-summary");
}

/**
 * Trigger discovery scan for new endpoints
 */
export async function triggerDiscovery(): Promise<DiscoveryResponse> {
  return post<DiscoveryResponse>("/api/sitemap/discover");
}

/**
 * Check health of a single sitemap entry
 */
export async function checkEntryHealth(id: number): Promise<HealthCheckResponse> {
  return post<HealthCheckResponse>(`/api/sitemap/check/${id}`);
}

/**
 * Check health of all sitemap entries (queues background task)
 */
export async function checkAllHealth(): Promise<{ status: string; task_id: string; message: string }> {
  return post("/api/sitemap/check-all");
}

/**
 * Register a new sitemap entry manually
 */
export async function registerEntry(data: {
  port: number;
  path: string;
  method?: string;
  entry_type?: string;
  title?: string;
}): Promise<SitemapEntry> {
  return post<SitemapEntry>("/api/sitemap/register", data);
}

/**
 * Delete a sitemap entry
 */
export async function deleteEntry(id: number): Promise<{ success: boolean; deleted_id: number }> {
  return del(`/api/sitemap/entries/${id}`);
}

// ============================================================================
// Maintenance Functions (for Status page)
// ============================================================================

/**
 * Get health history statistics
 */
export async function fetchHistoryStats(): Promise<HistoryStatsResponse> {
  return get<HistoryStatsResponse>("/api/sitemap/history-stats");
}

/**
 * Trigger cleanup of old health history
 */
export async function cleanupHistory(
  days: number = 7
): Promise<CleanupResponse> {
  return post<CleanupResponse>(`/api/sitemap/cleanup-history?days=${days}`);
}

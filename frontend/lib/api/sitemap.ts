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

import { del, get, post } from './client'

// ============================================================================
// Types
// ============================================================================

export type EntryType = 'frontend_page' | 'api_endpoint' | 'manual'
export type HealthStatus = 'healthy' | 'warning' | 'error' | 'unknown'

export interface SitemapEntry {
  id: number
  port: number
  path: string
  method: string
  entryType: EntryType
  source: string | null
  title: string | null
  parentPath: string | null
  healthStatus: HealthStatus
  consoleErrors: number
  consoleWarnings: number
  httpStatus: number | null
  responseTimeMs: number | null
  lastErrorMessage: string | null
  artifactId: number | null
  lastCheckedAt: string | null
  discoveredAt: string | null
}

export interface SitemapListResponse {
  total: number
  entries: SitemapEntry[]
}

export interface HealthSummaryResponse {
  total: number
  healthy: number
  warning: number
  error: number
  unknown: number
  byPort: Record<
    string,
    { healthy: number; warning: number; error: number; unknown: number }
  >
}

export interface SitemapFilters {
  port?: number
  healthStatus?: HealthStatus
  entryType?: EntryType
  limit?: number
  offset?: number
}

export interface DiscoveredPort {
  port: number
  serviceName: string
  serviceType: string
  source: string
  description: string | null
}

export interface DiscoveredPortsResponse {
  ports: DiscoveredPort[]
  backendPort: number
  frontendPort: number
}

export interface DiscoveryResponse {
  openapiDiscovered: number
  frontendDiscovered: number
  websocketDiscovered: number
  nextjsDiscovered: number
  apiImported: number
  totalSaved: number
}

export interface HealthCheckResponse {
  success: boolean
  entryId?: number
  healthStatus?: HealthStatus
  consoleErrors?: number
  consoleWarnings?: number
  httpStatus?: number
  responseTimeMs?: number
  error?: string
}

export interface HistoryStatsResponse {
  totalRows: number
  oldestEntry: string | null
  storageSize: string
}

export interface CleanupResponse {
  deleted: number
  retentionDays: number
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch sitemap entries with optional filters
 */
export async function fetchSitemapEntries(
  filters: SitemapFilters = {},
): Promise<SitemapListResponse> {
  const params = new URLSearchParams()
  if (filters.port) params.append('port', filters.port.toString())
  if (filters.healthStatus) params.append('health_status', filters.healthStatus)
  if (filters.entryType) params.append('entry_type', filters.entryType)
  if (filters.limit) params.append('limit', filters.limit.toString())
  if (filters.offset) params.append('offset', filters.offset.toString())

  const queryString = params.toString()
  return get<SitemapListResponse>(
    `/api/sitemap/entries${queryString ? `?${queryString}` : ''}`,
  )
}

/**
 * Fetch a single sitemap entry by ID
 */
export async function fetchSitemapEntry(id: number): Promise<SitemapEntry> {
  return get<SitemapEntry>(`/api/sitemap/entries/${id}`)
}

/**
 * Fetch aggregate health summary
 */
export async function fetchHealthSummary(): Promise<HealthSummaryResponse> {
  return get<HealthSummaryResponse>('/api/sitemap/health-summary')
}

/**
 * Trigger discovery scan for new endpoints
 */
export async function triggerDiscovery(): Promise<DiscoveryResponse> {
  return post<DiscoveryResponse>('/api/sitemap/discover')
}

/**
 * Check health of a single sitemap entry
 */
export async function checkEntryHealth(
  id: number,
): Promise<HealthCheckResponse> {
  return post<HealthCheckResponse>(`/api/sitemap/check/${id}`)
}

/**
 * Check health of all sitemap entries (queues background task)
 */
export async function checkAllHealth(): Promise<{
  status: string
  taskId: string
  message: string
}> {
  return post('/api/sitemap/check-all')
}

/**
 * Get discovered ports from systemd services
 */
export async function fetchDiscoveredPorts(): Promise<DiscoveredPortsResponse> {
  return get<DiscoveredPortsResponse>('/api/sitemap/ports')
}

/**
 * Register a new sitemap entry manually
 */
export async function registerEntry(data: {
  port: number
  path: string
  method?: string
  entry_type?: string
  title?: string
}): Promise<SitemapEntry> {
  return post<SitemapEntry>('/api/sitemap/register', data)
}

/**
 * Delete a sitemap entry
 */
export async function deleteEntry(
  id: number,
): Promise<{ success: boolean; deleted_id: number }> {
  return del(`/api/sitemap/entries/${id}`)
}

// ============================================================================
// Maintenance Functions (for Status page)
// ============================================================================

/**
 * Get health history statistics
 */
export async function fetchHistoryStats(): Promise<HistoryStatsResponse> {
  return get<HistoryStatsResponse>('/api/sitemap/history-stats')
}

/**
 * Trigger cleanup of old health history
 */
export async function cleanupHistory(
  days: number = 7,
): Promise<CleanupResponse> {
  return post<CleanupResponse>(`/api/sitemap/cleanup-history?days=${days}`)
}

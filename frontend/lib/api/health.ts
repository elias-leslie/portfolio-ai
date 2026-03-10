import { get } from './client'

export type HealthStatus = 'healthy' | 'degraded' | 'down'
export type CheckStatus = 'ok' | 'degraded' | 'down'

export interface HealthCheckResult {
  status: CheckStatus
  message: string | null
  responseTimeMs?: number | null
  latencyMs?: number | null
  details?: Record<string, unknown> | null
}

export interface SourceHealthCheck {
  status: CheckStatus
  lastSuccess?: string | null
  successRate?: number | null
  avgLatencyMs?: number | null
  rateLimitHits?: number
  inCooldown?: boolean
  cooldownRemainingSeconds?: number
}

export interface WorkerLikeStatus {
  active: boolean
  message?: string
  poolSize?: number | null
  activeTasks?: number | null
}

export interface WatchlistStats {
  totalItems: number
  lastRefresh?: string | null
  refreshAgeMinutes?: number | null
  itemsWithScores: number
}

export interface ApiQuotaInfo {
  sourceName: string
  configured: boolean
  rateLimit?: string | null
  dailyLimit?: string | null
  estimatedCapacity?: number | null
}

export interface WorkflowHealthInfo {
  status: 'healthy' | 'warning' | 'critical'
  totalWorkflows24h: number
  successfulWorkflows: number
  failedWorkflows: number
  blockedWorkflows: number
  successRate: number
  lastSuccessfulWorkflow?: string | null
  lastSuccessfulType?: string | null
  failuresByType: Record<string, number>
  blockedByType: Record<string, number>
}

export interface CacheStats {
  enabled?: boolean
  size?: number
  maxSize?: number
  ttlDefault?: number
  hits?: number
  misses?: number
  hitRate?: number
  invalidations?: number
  totalCached?: number
  cacheAgeMinutes?: number | null
}

export interface HealthServiceStatus {
  active?: boolean
  serviceName?: string
  status?: string
  message?: string
  pid?: number | null
  port?: number | null
}

export interface DataFreshnessStatus {
  lastCheck?: string | null
  status?: string
  message?: string
  tablesChecked?: number
  fresh?: number
  stale?: number
  critical?: number
  remediationsTriggered?: number
  error?: string
}

export interface RecentRemediation {
  tableName: string
  triggeredAt?: string | null
  status: string
  ageHours?: number | null
  thresholdHours?: number | null
  reason?: string | null
  errorMessage?: string | null
}

export interface DetailedHealthCheckResponse {
  status: HealthStatus
  timestamp: string
  version: string
  uptimeSeconds: number
  checks: Record<string, HealthCheckResult>
  sources: Record<string, SourceHealthCheck>
  services: Record<string, HealthServiceStatus>
  cacheStats?: CacheStats | null
  watchlistStats?: WatchlistStats | null
  apiQuotas: ApiQuotaInfo[]
  workflowHealth?: WorkflowHealthInfo | null
  dataFreshnessStatus?: DataFreshnessStatus
  recentRemediations: RecentRemediation[]
}

export async function fetchDetailedHealth(): Promise<DetailedHealthCheckResponse> {
  return get<DetailedHealthCheckResponse>('/health/detailed')
}

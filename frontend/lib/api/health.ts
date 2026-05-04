import { get, post } from './client'

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
  statusReason?: string | null
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
  checkStatus?: string
  message?: string
  tablesChecked?: number
  fresh?: number
  stale?: number
  critical?: number
  remediationsTriggered?: number
  error?: string
}

export interface DataFreshnessCoverage {
  requiredSymbols?: number
  currentSymbols?: number
  expectedDate?: string
  staleSymbols?: string[]
  missingSymbols?: string[]
  staleSymbolCount?: number
}

export interface DataFreshnessDetail {
  tableName: string
  lastUpdate?: string | null
  ageHours?: number | null
  isStale: boolean
  isCritical: boolean
  reason?: string | null
  coverage?: DataFreshnessCoverage | null
}

export interface LiveFreshnessResponse {
  status: 'success' | 'warning' | 'critical' | 'error' | string
  message: string
  generatedAt: string
  tablesChecked: number
  fresh: number
  stale: number
  critical: number
  alertsCreated?: number
  remediationsTriggered?: number
  details: DataFreshnessDetail[]
  remediationCooldowns?: Record<string, string>
  recentRemediations?: RecentRemediation[]
}

export type DecisionDataDomainStatus =
  | 'current'
  | 'aging'
  | 'stale'
  | 'missing'
  | 'disabled'
  | 'quotaLimited'
  | 'quota_limited'
  | 'degraded'
  | 'unknown'

export type DecisionDataDomainSeverity =
  | 'healthy'
  | 'warning'
  | 'critical'
  | 'unknown'

export interface DecisionDataDomain {
  key: string
  label: string
  status: DecisionDataDomainStatus
  severity: DecisionDataDomainSeverity
  message: string
  lastUpdated?: string | null
  evidence: Record<string, unknown>
}

export interface DecisionDataHealth {
  status: 'healthy' | 'degraded' | 'critical' | 'unknown'
  message: string
  domains: DecisionDataDomain[]
}

export interface RecentRemediation {
  tableName: string
  triggeredAt?: string | null
  status: string
  ageHours?: number | null
  thresholdHours?: number | null
  reason?: string | null
  errorMessage?: string | null
  occurrenceCount?: number | null
  resolved?: boolean
  resolvedAt?: string | null
}

export interface StaleMaintenanceRun {
  taskName: string
  startedAt?: string | null
  dryRun: boolean
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
  decisionDataHealth?: DecisionDataHealth
  recentRemediations: RecentRemediation[]
  staleMaintenanceRuns: StaleMaintenanceRun[]
}

export async function fetchDetailedHealth(): Promise<DetailedHealthCheckResponse> {
  return get<DetailedHealthCheckResponse>('/health/detailed')
}

export async function fetchLiveFreshness(): Promise<LiveFreshnessResponse> {
  return get<LiveFreshnessResponse>('/health/freshness')
}

export async function refreshLiveFreshness(): Promise<LiveFreshnessResponse> {
  return post<LiveFreshnessResponse>('/health/freshness/refresh')
}

/**
 * API client for System Capabilities Registry
 */

import { get, post } from './client'

/**
 * Capability Types
 */
export type CapabilityType = 'db' | 'celery' | 'api'

export type InsightSeverity = 'low' | 'medium' | 'high' | 'critical'
export type InsightStatus =
  | 'pending'
  | 'confirmed'
  | 'dismissed'
  | 'in_progress'
  | 'fixed'
export type NoteType =
  | 'observation'
  | 'recommendation'
  | 'question'
  | 'decision'
  | 'reference'

/**
 * Base Capability (common fields across all types)
 */
export interface BaseCapability {
  id: number
  capabilityType: CapabilityType
  insightsCount: number
  notesCount: number
  createdAt: string
  updatedAt: string
}

/**
 * Database Table Capability
 */
export interface DbCapability extends BaseCapability {
  capabilityType: 'db'
  tableName: string
  category: string
  rowCount: number | null
  columns: string[] | null
  lastUpdated: string | null
  ageHours: number | null
  freshnessStatus: 'fresh' | 'stale' | 'critical' | 'unknown'
  expectedRefreshHours: number
  description: string
  source: string | null
  healthStatus: string
}

/**
 * Celery Task Capability
 */
export interface CeleryCapability extends BaseCapability {
  capabilityType: 'celery'
  taskName: string
  category: string
  scheduleType: string | null
  scheduleInterval: string | null
  scheduleDescription: string | null
  scheduleCrontab: string | null
  scheduleIntervalSeconds: number | null
  description: string
  populatesTables: string[]
  dependsOnTasks: string[]
  lastRunAt: string | null
  lastRunStatus: string | null
  nextRunAt: string | null
  successCount7D: number | null
  failureCount7D: number | null
  successRatePct: number | null
  avgDurationMs: number | null
  maxDurationMs: number | null
  taskPath: string | null
  functionName: string | null
  healthStatus: string
}

/**
 * API Endpoint Capability
 */
export interface ApiCapability extends BaseCapability {
  capabilityType: 'api'
  endpointPath: string
  httpMethod: string
  category: string
  description: string
  dependsOnTables: string[]
  responseFormat: string | null
  routeFile: string | null
  functionName: string | null
  avgResponseTimeMs: number | null
  p95ResponseTimeMs: number | null
  p99ResponseTimeMs: number | null
  errorRatePct: number | null
  last7DRequestCount: number | null
  healthStatus: string
}

/**
 * Union type for all capabilities
 */
export type Capability = DbCapability | CeleryCapability | ApiCapability

/**
 * Capability Insight
 */
export interface CapabilityInsight {
  id: number
  capabilityType: CapabilityType
  capabilityId: number | null
  tableName: string | null
  taskName: string | null
  endpointPath: string | null
  insightType: string
  severity: InsightSeverity
  finding: string
  impact: string | null
  suggestedFix: string | null
  confidence: number
  status: InsightStatus
  statusReason: string | null
  reviewedBy: string | null
  reviewedAt: string | null
  fixedAt: string | null
  generatedAt: string
  updatedAt: string
  relatedTable?: string
}

/**
 * Capability Note
 */
export interface CapabilityNote {
  id: number
  capabilityType: CapabilityType
  capabilityId: number | null
  insightId: number | null
  noteType: NoteType
  note: string
  createdBy: string
  createdAt: string
}

/**
 * API Response Types
 */
export interface CapabilitiesListResponse {
  total: number
  capabilities: Capability[]
}

export interface CapabilityDetailResponse {
  capability: Capability
  insights: CapabilityInsight[]
  notes: CapabilityNote[]
  dependencies: {
    populatesTables?: string[]
    dependsOnTasks?: string[]
    dependsOnTables?: string[]
  }
}

export interface InsightsListResponse {
  total: number
  pendingCount: number // Actionable items (not fixed/dismissed)
  fixedCount: number // Completed items
  insights: CapabilityInsight[]
}

export interface NotesListResponse {
  notes: CapabilityNote[]
}

export interface ScanTriggerResponse {
  taskId: string
  status: string
  message: string
}

export interface InsightReviewRequest {
  status: InsightStatus
  statusReason?: string
  reviewedBy?: string
}

export interface NoteCreateRequest {
  capabilityType: CapabilityType
  capabilityId?: number
  insightId?: number
  noteType: NoteType
  note: string
}

/**
 * Filters for capabilities list
 */
export interface CapabilitiesFilters {
  type?: 'all' | CapabilityType
  category?: string
  status?: string
  limit?: number
  offset?: number
}

/**
 * Filters for insights list
 */
export interface InsightsFilters {
  status?: InsightStatus
  severity?: InsightSeverity
  type?: string
  limit?: number
  offset?: number
}

/**
 * API Functions
 */

/**
 * Fetch paginated list of capabilities
 */
export async function fetchCapabilities(
  filters: CapabilitiesFilters = {},
): Promise<CapabilitiesListResponse> {
  const params = new URLSearchParams()

  if (filters.type) params.append('type', filters.type)
  if (filters.category) params.append('category', filters.category)
  if (filters.status) params.append('status', filters.status)
  if (filters.limit) params.append('limit', filters.limit.toString())
  if (filters.offset) params.append('offset', filters.offset.toString())

  const queryString = params.toString()
  const url = `/api/capabilities/${queryString ? `?${queryString}` : ''}`

  return get<CapabilitiesListResponse>(url)
}

/**
 * Fetch detailed view of a single capability
 */
export async function fetchCapabilityDetail(
  capabilityType: CapabilityType,
  capabilityId: number,
): Promise<CapabilityDetailResponse> {
  return get<CapabilityDetailResponse>(
    `/api/capabilities/${capabilityType}/${capabilityId}`,
  )
}

/**
 * Fetch paginated list of insights
 */
export async function fetchInsights(
  filters: InsightsFilters = {},
): Promise<InsightsListResponse> {
  const params = new URLSearchParams()

  if (filters.status) params.append('status', filters.status)
  if (filters.severity) params.append('severity', filters.severity)
  if (filters.type) params.append('type', filters.type)
  if (filters.limit) params.append('limit', filters.limit.toString())
  if (filters.offset) params.append('offset', filters.offset.toString())

  const queryString = params.toString()
  const url = `/api/capabilities/insights/${queryString ? `?${queryString}` : ''}`

  return get<InsightsListResponse>(url)
}

/**
 * Review/update an insight's status
 */
export async function reviewInsight(
  insightId: number,
  data: InsightReviewRequest,
): Promise<{ id: number; status: string; message: string }> {
  return post(`/api/capabilities/insights/${insightId}/review`, data)
}

/**
 * Create a new capability note
 */
export async function createNote(
  data: NoteCreateRequest,
): Promise<{ id: number; message: string }> {
  return post('/api/capabilities/notes', data)
}

/**
 * Fetch notes filtered by capability or insight
 */
export async function fetchNotes(filters: {
  capability_type?: CapabilityType
  capability_id?: number
  insight_id?: number
}): Promise<NotesListResponse> {
  const params = new URLSearchParams()

  if (filters.capability_type)
    params.append('capability_type', filters.capability_type)
  if (filters.capability_id)
    params.append('capability_id', filters.capability_id.toString())
  if (filters.insight_id)
    params.append('insight_id', filters.insight_id.toString())

  const queryString = params.toString()
  const url = `/api/capabilities/notes/${queryString ? `?${queryString}` : ''}`

  return get<NotesListResponse>(url)
}

/**
 * Trigger a manual system capabilities scan
 */
export async function triggerScan(): Promise<ScanTriggerResponse> {
  return post('/api/capabilities/scan')
}

/**
 * API client for QA System
 */

import { get, patch, post } from './client'

/**
 * QA Issue Types
 */
export type QACategory =
  | 'style'
  | 'type'
  | 'performance'
  | 'security'
  | 'reliability'
  | 'maintainability'
  | 'api-contract'
  | 'data-quality'
  | 'test-coverage'

export type QASeverity = 'low' | 'medium' | 'high' | 'critical'

/**
 * QA Issue Interface
 */
export interface QAIssue {
  id: string
  category: QACategory
  severity: QASeverity
  filePath: string
  lineNumber: number | null
  description: string
  suggestion: string | null
  detectedAt: string
  resolvedAt: string | null
  resolvedBy: string | null
  isFalsePositive: boolean
  falsePositiveNotes: string | null
}

/**
 * QA Summary Interface
 */
export interface QASummary {
  totalIssues: number
  criticalCount: number
  highCount: number
  mediumCount: number
  lowCount: number
  resolvedThisWeek: number
  addedThisWeek: number
  byCategory: Record<QACategory, number>
  bySeverity: Record<QASeverity, number>
  resolutionRate: number
}

/**
 * QA Issues List Response
 */
export interface QAIssuesResponse {
  total: number
  issues: QAIssue[]
}

/**
 * QA Trend Data Point
 */
export interface QATrendDataPoint {
  date: string
  total: number
  critical: number
  resolved: number
  added: number
}

/**
 * QA Trends Response
 */
export interface QATrendsResponse {
  trends: QATrendDataPoint[]
}

/**
 * QA Scan Response
 */
export interface QAScanResponse {
  taskId: string
  status: string
  message: string
  categoriesScanned: string[]
}

/**
 * Filters for QA issues list
 */
export interface QAIssuesFilters {
  category?: QACategory
  severity?: QASeverity
  resolved?: boolean
  limit?: number
  offset?: number
}

/**
 * Resolve issue request
 */
export interface ResolveIssueRequest {
  resolvedBy: string
  notes?: string
}

/**
 * Mark false positive request
 */
export interface MarkFalsePositiveRequest {
  notes?: string
}

/**
 * API Functions
 */

/**
 * Fetch QA summary statistics
 */
export async function fetchQASummary(): Promise<QASummary> {
  return get<QASummary>('/api/qa/summary')
}

/**
 * Fetch paginated list of QA issues
 */
export async function fetchQAIssues(
  filters: QAIssuesFilters = {},
): Promise<QAIssuesResponse> {
  const params = new URLSearchParams()

  if (filters.category) params.append('category', filters.category)
  if (filters.severity) params.append('severity', filters.severity)
  if (filters.resolved !== undefined)
    params.append('resolved', filters.resolved.toString())
  if (filters.limit) params.append('limit', filters.limit.toString())
  if (filters.offset) params.append('offset', filters.offset.toString())

  const queryString = params.toString()
  const url = `/api/qa/issues${queryString ? `?${queryString}` : ''}`

  return get<QAIssuesResponse>(url)
}

/**
 * Fetch QA trends over time
 */
export async function fetchQATrends(
  days: number = 30,
): Promise<QATrendsResponse> {
  return get<QATrendsResponse>(`/api/qa/trends?days=${days}`)
}

/**
 * Trigger a QA scan
 */
export async function triggerQAScan(
  categories?: QACategory[],
): Promise<QAScanResponse> {
  const body = categories ? { categories } : {}
  return post<QAScanResponse>('/api/qa/scan', body)
}

/**
 * Resolve a QA issue
 */
export async function resolveQAIssue(
  issueId: string,
  data: ResolveIssueRequest,
): Promise<{ id: string; status: string; message: string }> {
  return patch<{ id: string; status: string; message: string }>(
    `/api/qa/issues/${issueId}/resolve`,
    data,
  )
}

/**
 * Mark a QA issue as false positive
 */
export async function markFalsePositive(
  issueId: string,
  data: MarkFalsePositiveRequest,
): Promise<{ id: string; status: string; message: string }> {
  return patch<{ id: string; status: string; message: string }>(
    `/api/qa/issues/${issueId}/false-positive`,
    data,
  )
}

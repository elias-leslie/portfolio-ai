/**
 * API client for System Capabilities Registry
 */

import { get, post } from "./client";

/**
 * Capability Types
 */
export type CapabilityType = "db" | "celery" | "api";

export type InsightSeverity = "low" | "medium" | "high" | "critical";
export type InsightStatus = "pending" | "confirmed" | "dismissed" | "in_progress" | "fixed";
export type NoteType = "observation" | "recommendation" | "question" | "decision" | "reference";

/**
 * Base Capability (common fields across all types)
 */
export interface BaseCapability {
  id: number;
  capability_type: CapabilityType;
  insights_count: number;
  notes_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * Database Table Capability
 */
export interface DbCapability extends BaseCapability {
  capability_type: "db";
  table_name: string;
  category: string;
  row_count: number | null;
  columns: string[] | null;
  last_updated: string | null;
  age_hours: number | null;
  freshness_status: "fresh" | "stale" | "critical" | "unknown";
  expected_refresh_hours: number;
  description: string;
  source: string | null;
}

/**
 * Celery Task Capability
 */
export interface CeleryCapability extends BaseCapability {
  capability_type: "celery";
  task_name: string;
  category: string;
  schedule_type: string | null;
  schedule_interval: string | null;
  description: string;
  populates_tables: string[];
  depends_on_tasks: string[];
  last_run_at: string | null;
  last_run_status: string | null;
}

/**
 * API Endpoint Capability
 */
export interface ApiCapability extends BaseCapability {
  capability_type: "api";
  endpoint_path: string;
  http_method: string;
  category: string;
  description: string;
  depends_on_tables: string[];
  response_format: string | null;
}

/**
 * Union type for all capabilities
 */
export type Capability = DbCapability | CeleryCapability | ApiCapability;

/**
 * Capability Insight
 */
export interface CapabilityInsight {
  id: number;
  capability_type: CapabilityType;
  capability_id: number | null;
  table_name: string | null;
  task_name: string | null;
  endpoint_path: string | null;
  insight_type: string;
  severity: InsightSeverity;
  finding: string;
  impact: string | null;
  suggested_fix: string | null;
  confidence: number;
  status: InsightStatus;
  status_reason: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  fixed_at: string | null;
  generated_at: string;
  updated_at: string;
  related_table?: string;
}

/**
 * Capability Note
 */
export interface CapabilityNote {
  id: number;
  capability_type: CapabilityType;
  capability_id: number | null;
  insight_id: number | null;
  note_type: NoteType;
  note: string;
  created_by: string;
  created_at: string;
}

/**
 * API Response Types
 */
export interface CapabilitiesListResponse {
  total: number;
  capabilities: Capability[];
}

export interface CapabilityDetailResponse {
  capability: Capability;
  insights: CapabilityInsight[];
  notes: CapabilityNote[];
  dependencies: {
    populates_tables?: string[];
    depends_on_tasks?: string[];
    depends_on_tables?: string[];
  };
}

export interface InsightsListResponse {
  total: number;
  insights: CapabilityInsight[];
}

export interface NotesListResponse {
  notes: CapabilityNote[];
}

export interface ScanTriggerResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface InsightReviewRequest {
  status: InsightStatus;
  status_reason?: string;
  reviewed_by?: string;
}

export interface NoteCreateRequest {
  capability_type: CapabilityType;
  capability_id?: number;
  insight_id?: number;
  note_type: NoteType;
  note: string;
}

/**
 * Filters for capabilities list
 */
export interface CapabilitiesFilters {
  type?: "all" | CapabilityType;
  category?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

/**
 * Filters for insights list
 */
export interface InsightsFilters {
  status?: InsightStatus;
  severity?: InsightSeverity;
  type?: string;
  limit?: number;
  offset?: number;
}

/**
 * API Functions
 */

/**
 * Fetch paginated list of capabilities
 */
export async function fetchCapabilities(
  filters: CapabilitiesFilters = {}
): Promise<CapabilitiesListResponse> {
  const params = new URLSearchParams();

  if (filters.type) params.append("type", filters.type);
  if (filters.category) params.append("category", filters.category);
  if (filters.status) params.append("status", filters.status);
  if (filters.limit) params.append("limit", filters.limit.toString());
  if (filters.offset) params.append("offset", filters.offset.toString());

  const queryString = params.toString();
  const url = `/api/capabilities${queryString ? `?${queryString}` : ""}`;

  return get<CapabilitiesListResponse>(url);
}

/**
 * Fetch detailed view of a single capability
 */
export async function fetchCapabilityDetail(
  capabilityType: CapabilityType,
  capabilityId: number
): Promise<CapabilityDetailResponse> {
  return get<CapabilityDetailResponse>(`/api/capabilities/${capabilityType}/${capabilityId}`);
}

/**
 * Fetch paginated list of insights
 */
export async function fetchInsights(
  filters: InsightsFilters = {}
): Promise<InsightsListResponse> {
  const params = new URLSearchParams();

  if (filters.status) params.append("status", filters.status);
  if (filters.severity) params.append("severity", filters.severity);
  if (filters.type) params.append("type", filters.type);
  if (filters.limit) params.append("limit", filters.limit.toString());
  if (filters.offset) params.append("offset", filters.offset.toString());

  const queryString = params.toString();
  const url = `/api/capabilities/insights${queryString ? `?${queryString}` : ""}`;

  return get<InsightsListResponse>(url);
}

/**
 * Review/update an insight's status
 */
export async function reviewInsight(
  insightId: number,
  data: InsightReviewRequest
): Promise<{ id: number; status: string; message: string }> {
  return post(`/api/capabilities/insights/${insightId}/review`, data);
}

/**
 * Create a new capability note
 */
export async function createNote(
  data: NoteCreateRequest
): Promise<{ id: number; message: string }> {
  return post("/api/capabilities/notes", data);
}

/**
 * Fetch notes filtered by capability or insight
 */
export async function fetchNotes(filters: {
  capability_type?: CapabilityType;
  capability_id?: number;
  insight_id?: number;
}): Promise<NotesListResponse> {
  const params = new URLSearchParams();

  if (filters.capability_type) params.append("capability_type", filters.capability_type);
  if (filters.capability_id) params.append("capability_id", filters.capability_id.toString());
  if (filters.insight_id) params.append("insight_id", filters.insight_id.toString());

  const queryString = params.toString();
  const url = `/api/capabilities/notes${queryString ? `?${queryString}` : ""}`;

  return get<NotesListResponse>(url);
}

/**
 * Trigger a manual system capabilities scan
 */
export async function triggerScan(): Promise<ScanTriggerResponse> {
  return post("/api/capabilities/scan");
}

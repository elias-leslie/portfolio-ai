/**
 * Agent telemetry API client
 *
 * Provides functions for fetching agent telemetry data:
 * - Summary statistics (tokens, costs, latency)
 * - Run history with filtering
 * - Provider comparison metrics
 */

import { get } from "./client";

export interface TokenUsage {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
}

export interface ProviderMetrics {
  provider: string;
  totalRuns: number;
  successfulRuns: number;
  failedRuns: number;
  successRate: number;
  totalTokens: number;
  avgTokensPerRun: number;
  avgDurationMs: number;
  totalCostUsd: number;
}

export interface DailyTelemetry {
  date: string;
  totalRuns: number;
  successfulRuns: number;
  failedRuns: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalTokens: number;
  avgDurationMs: number;
  estimatedCostUsd: number;
}

export interface TelemetrySummary {
  periodStart: string;
  periodEnd: string;
  periodDays: number;
  totalRuns: number;
  successfulRuns: number;
  failedRuns: number;
  successRate: number;
  totalInputTokens: number;
  totalOutputTokens: number;
  totalTokens: number;
  avgTokensPerRun: number;
  avgDurationMs: number;
  totalCostUsd: number;
  byProvider: ProviderMetrics[];
  dailyData: DailyTelemetry[];
}

export interface AgentRunDetail {
  id: string;
  agentType: string;
  startedAt: string;
  completedAt: string | null;
  status: string;
  provider: string | null;
  model: string | null;
  durationMs: number | null;
  tokenUsage: TokenUsage | null;
  error: string | null;
}

export interface RunHistoryResponse {
  runs: AgentRunDetail[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Fetch telemetry summary for a specified period
 */
export async function fetchTelemetrySummary(
  days: number = 7
): Promise<TelemetrySummary> {
  return get<TelemetrySummary>(`/api/agents/telemetry/summary?days=${days}`);
}

/**
 * Fetch paginated run history with optional filters
 */
export async function fetchRunHistory(params: {
  limit?: number;
  offset?: number;
  provider?: string;
  status?: string;
  agent_type?: string;
}): Promise<RunHistoryResponse> {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set("limit", params.limit.toString());
  if (params.offset) searchParams.set("offset", params.offset.toString());
  if (params.provider) searchParams.set("provider", params.provider);
  if (params.status) searchParams.set("status", params.status);
  if (params.agent_type) searchParams.set("agent_type", params.agent_type);

  return get<RunHistoryResponse>(
    `/api/agents/telemetry/history?${searchParams.toString()}`
  );
}

/**
 * Fetch provider comparison metrics
 */
export async function fetchProviderComparison(
  days: number = 30
): Promise<ProviderMetrics[]> {
  return get<ProviderMetrics[]>(`/api/agents/telemetry/providers?days=${days}`);
}

/**
 * Fetch details for a specific run
 */
export async function fetchRunDetail(
  runId: string
): Promise<AgentRunDetail | null> {
  try {
    return await get<AgentRunDetail>(`/api/agents/runs/${runId}`);
  } catch {
    return null;
  }
}

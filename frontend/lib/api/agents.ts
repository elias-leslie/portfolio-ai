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
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface ProviderMetrics {
  provider: string;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  total_tokens: number;
  avg_tokens_per_run: number;
  avg_duration_ms: number;
  total_cost_usd: number;
}

export interface DailyTelemetry {
  date: string;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  avg_duration_ms: number;
  estimated_cost_usd: number;
}

export interface TelemetrySummary {
  period_start: string;
  period_end: string;
  period_days: number;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  success_rate: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  avg_tokens_per_run: number;
  avg_duration_ms: number;
  total_cost_usd: number;
  by_provider: ProviderMetrics[];
  daily_data: DailyTelemetry[];
}

export interface AgentRunDetail {
  id: string;
  agent_type: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  provider: string | null;
  model: string | null;
  duration_ms: number | null;
  token_usage: TokenUsage | null;
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

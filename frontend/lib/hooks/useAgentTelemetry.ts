/**
 * React Query hooks for agent telemetry data
 */

import { useQuery } from '@tanstack/react-query'
import {
  type AgentRunDetail,
  fetchProviderComparison,
  fetchRunDetail,
  fetchRunHistory,
  fetchTelemetrySummary,
  type ProviderMetrics,
  type RunHistoryResponse,
  type TelemetrySummary,
} from '@/lib/api/agents'

// Query keys for cache management
export const agentTelemetryKeys = {
  all: ['agent-telemetry'] as const,
  summary: (days: number) =>
    [...agentTelemetryKeys.all, 'summary', days] as const,
  history: (params: {
    limit?: number
    offset?: number
    provider?: string
    status?: string
    agent_type?: string
  }) => [...agentTelemetryKeys.all, 'history', params] as const,
  providers: (days: number) =>
    [...agentTelemetryKeys.all, 'providers', days] as const,
  run: (runId: string) => [...agentTelemetryKeys.all, 'run', runId] as const,
}

/**
 * Hook to fetch telemetry summary
 */
export function useTelemetrySummary(days: number = 7) {
  return useQuery<TelemetrySummary, Error>({
    queryKey: agentTelemetryKeys.summary(days),
    queryFn: () => fetchTelemetrySummary(days),
    staleTime: 60 * 1000, // 1 minute
    refetchInterval: 60 * 1000, // Refetch every minute
  })
}

/**
 * Hook to fetch run history with pagination and filters
 */
export function useRunHistory(
  params: {
    limit?: number
    offset?: number
    provider?: string
    status?: string
    agent_type?: string
  } = {},
) {
  return useQuery<RunHistoryResponse, Error>({
    queryKey: agentTelemetryKeys.history(params),
    queryFn: () => fetchRunHistory(params),
    staleTime: 30 * 1000, // 30 seconds
  })
}

/**
 * Hook to fetch provider comparison metrics
 */
export function useProviderComparison(days: number = 30) {
  return useQuery<ProviderMetrics[], Error>({
    queryKey: agentTelemetryKeys.providers(days),
    queryFn: () => fetchProviderComparison(days),
    staleTime: 5 * 60 * 1000, // 5 minutes
  })
}

/**
 * Hook to fetch a specific run detail
 */
export function useRunDetail(runId: string | null) {
  return useQuery<AgentRunDetail | null, Error>({
    queryKey: agentTelemetryKeys.run(runId ?? ''),
    queryFn: () => (runId ? fetchRunDetail(runId) : Promise.resolve(null)),
    enabled: !!runId,
    staleTime: 5 * 60 * 1000, // 5 minutes (run details don't change)
  })
}

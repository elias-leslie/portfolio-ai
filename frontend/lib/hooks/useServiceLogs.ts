/**
 * React Query hook for service log fetching
 */

import { useQuery } from '@tanstack/react-query'
import { fetchServiceLogs } from '../api/status'

/**
 * Hook to fetch logs for a specific service
 *
 * Only fetches when enabled (typically when log viewer is expanded)
 * Auto-refreshes every 5 seconds when enabled
 */
export function useServiceLogs(service: string, enabled: boolean = false) {
  return useQuery({
    queryKey: ['service-logs', service],
    queryFn: () => fetchServiceLogs(service, 100),
    enabled, // Only fetch when enabled (e.g., log viewer expanded)
    refetchInterval: enabled ? 5000 : false, // Poll every 5s when enabled
    staleTime: 0,
    gcTime: 10000,
    retry: 1, // Fewer retries for log fetching
  })
}

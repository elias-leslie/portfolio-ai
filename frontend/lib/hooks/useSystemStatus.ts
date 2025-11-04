/**
 * React Query hook for system status polling
 */

import { useQuery } from "@tanstack/react-query";
import { fetchSystemStatus } from "../api/status";

/**
 * Hook to fetch system status with auto-refresh polling
 *
 * Polls the health endpoint every 5 seconds for real-time status updates
 */
export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: fetchSystemStatus,
    refetchInterval: 5000, // Poll every 5 seconds
    staleTime: 0, // Always consider data stale to enable polling
    gcTime: 10000, // Cache for 10 seconds (renamed from cacheTime in v5)
    retry: 2, // Retry failed requests twice
    retryDelay: 1000, // Wait 1s between retries
  });
}

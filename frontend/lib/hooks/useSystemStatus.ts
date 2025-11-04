/**
 * React Query hook for system status polling
 */

import { useQuery } from "@tanstack/react-query";
import { fetchSystemStatus } from "../api/status";

/**
 * Hook to fetch system status with auto-refresh polling
 *
 * Polls the health endpoint every 30 seconds (reduced from 5s to prevent overload)
 */
export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status"],
    queryFn: fetchSystemStatus,
    refetchInterval: 30000, // Poll every 30 seconds (was 5s, caused overload)
    staleTime: 0, // Always consider data stale to enable polling
    gcTime: 40000, // Cache for 40 seconds (renamed from cacheTime in v5)
    retry: 1, // Retry failed requests once (reduced from 2)
    retryDelay: 2000, // Wait 2s between retries (increased from 1s)
  });
}

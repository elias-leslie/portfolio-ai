/**
 * TanStack Query hook for Fear & Greed Index
 */

import { useQuery, UseQueryResult } from "@tanstack/react-query";
import { fetchFearGreed } from "../api/market";
import type { FearGreedResponse } from "../api/market";

/**
 * Hook to fetch Fear & Greed Index reading
 * Updates daily, with hourly refetch to catch new data
 */
export function useFearGreed(
  date?: string,
  includeComponents?: boolean
): UseQueryResult<FearGreedResponse> {
  return useQuery({
    queryKey: ["market", "fear-greed", date, includeComponents],
    queryFn: () => fetchFearGreed(date, includeComponents),
    staleTime: 1000 * 60 * 60, // 1 hour (data updates daily)
    refetchInterval: 1000 * 60 * 60 * 4, // Refetch every 4 hours
    retry: 2,
  });
}

/**
 * React Query hooks for disagreement detection data
 */

import { useQuery } from "@tanstack/react-query";
import {
  getDisagreements,
  getDisagreementStats,
  getSymbolDisagreements,
  type DisagreementsResponse,
  type DisagreementStats,
} from "@/lib/api/disagreements";

// Query keys
export const disagreementKeys = {
  all: ["disagreements"] as const,
  lists: () => [...disagreementKeys.all, "list"] as const,
  list: (days: number, severity?: "minor" | "major") =>
    [...disagreementKeys.lists(), days, severity] as const,
  stats: (days: number) => [...disagreementKeys.all, "stats", days] as const,
  symbol: (symbol: string, days: number) =>
    [...disagreementKeys.all, "symbol", symbol, days] as const,
};

/**
 * Hook to fetch recent disagreements
 *
 * @param days - Number of days to look back (default 7)
 * @param severity - Filter by severity (minor, major, or undefined for all)
 * @param limit - Maximum results (default 50)
 */
export function useDisagreements(
  days: number = 7,
  severity?: "minor" | "major",
  limit: number = 50
) {
  return useQuery<DisagreementsResponse>({
    queryKey: disagreementKeys.list(days, severity),
    queryFn: () => getDisagreements(days, severity, limit),
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * Hook to fetch disagreement statistics and trends
 *
 * @param days - Number of days to analyze (default 30)
 */
export function useDisagreementStats(days: number = 30) {
  return useQuery<DisagreementStats>({
    queryKey: disagreementKeys.stats(days),
    queryFn: () => getDisagreementStats(days),
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * Hook to fetch disagreements for a specific symbol
 *
 * @param symbol - Stock symbol
 * @param days - Number of days to look back (default 30)
 * @param enabled - Whether to enable the query (default true)
 */
export function useSymbolDisagreements(
  symbol: string,
  days: number = 30,
  enabled: boolean = true
) {
  return useQuery<DisagreementsResponse>({
    queryKey: disagreementKeys.symbol(symbol, days),
    queryFn: () => getSymbolDisagreements(symbol, days),
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 30, // 30 minutes
    enabled: enabled && !!symbol,
  });
}

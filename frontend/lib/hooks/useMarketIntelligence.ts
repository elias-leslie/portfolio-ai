/**
 * React Query hook for Market Intelligence API
 */

import { useQuery, UseQueryResult } from "@tanstack/react-query";
import {
  fetchMarketIntelligence,
  type MarketIntelligenceResponse,
} from "../api/market";

/**
 * Hook to fetch unified market intelligence
 * (narrative + dual scoring + sector rotation)
 */
export function useMarketIntelligence(): UseQueryResult<MarketIntelligenceResponse> {
  return useQuery({
    queryKey: ["market", "intelligence"],
    queryFn: fetchMarketIntelligence,
    staleTime: 1000 * 60 * 15, // 15 minutes
    refetchInterval: 1000 * 60 * 15, // Refetch every 15 minutes
    refetchOnWindowFocus: false, // Data doesn't change that fast
  });
}

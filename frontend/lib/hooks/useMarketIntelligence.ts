/**
 * React Query hooks for Market Intelligence API
 */

import { useQuery, UseQueryResult } from "@tanstack/react-query";
import {
  fetchMarketIntelligence,
  fetchFearGreedHistory,
  fetchIndicatorHistory,
  fetchSectorHistory,
  type MarketIntelligenceResponse,
  type FearGreedHistoryResponse,
  type IndicatorHistoryResponse,
  type SectorHistoryResponse,
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

/**
 * Hook to fetch Fear & Greed historical data for trend charts
 */
export function useFearGreedHistory(
  days: number = 365
): UseQueryResult<FearGreedHistoryResponse> {
  return useQuery({
    queryKey: ["market", "fear-greed-history", days],
    queryFn: () => fetchFearGreedHistory(days),
    staleTime: 1000 * 60 * 30, // 30 minutes
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to fetch key indicator historical data for trend charts
 */
export function useIndicatorHistory(
  days: number = 365
): UseQueryResult<IndicatorHistoryResponse> {
  return useQuery({
    queryKey: ["market", "indicator-history", days],
    queryFn: () => fetchIndicatorHistory(days),
    staleTime: 1000 * 60 * 30, // 30 minutes
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to fetch sector ETF historical data for performance charts
 */
export function useSectorHistory(
  days: number = 365
): UseQueryResult<SectorHistoryResponse> {
  return useQuery({
    queryKey: ["market", "sector-history", days],
    queryFn: () => fetchSectorHistory(days),
    staleTime: 1000 * 60 * 30, // 30 minutes
    refetchOnWindowFocus: false,
  });
}

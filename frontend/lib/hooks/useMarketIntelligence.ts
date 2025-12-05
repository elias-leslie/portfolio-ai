/**
 * React Query hooks for Market Intelligence API
 */

import { useQuery, UseQueryResult } from "@tanstack/react-query";
import {
  fetchMarketIntelligence,
  fetchFearGreedHistory,
  fetchNewsSentimentHistory,
  fetchIndicatorHistory,
  fetchSectorHistory,
  type MarketIntelligenceResponse,
  type FearGreedHistoryResponse,
  type NewsSentimentHistoryResponse,
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
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useFearGreedHistory(
  days: number = 365
): UseQueryResult<FearGreedHistoryResponse> {
  return useQuery({
    queryKey: ["market", "fear-greed-history", days],
    queryFn: () => fetchFearGreedHistory(days),
    staleTime: 1000 * 60 * 2, // 2 minutes - consider stale quickly
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  });
}

/**
 * Hook to fetch news sentiment historical data for trend charts
 * @param days - Number of days of history
 * @param granularity - 'daily' or 'hourly' (hourly useful for intraday view)
 */
export function useNewsSentimentHistory(
  days: number = 30,
  granularity: "daily" | "hourly" = "daily"
): UseQueryResult<NewsSentimentHistoryResponse> {
  return useQuery({
    queryKey: ["market", "news-sentiment-history", days, granularity],
    queryFn: () => fetchNewsSentimentHistory(days, granularity),
    staleTime: 1000 * 60 * 2, // 2 minutes
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true,
  });
}

/**
 * Hook to fetch key indicator historical data for trend charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useIndicatorHistory(
  days: number = 365
): UseQueryResult<IndicatorHistoryResponse> {
  return useQuery({
    queryKey: ["market", "indicator-history", days],
    queryFn: () => fetchIndicatorHistory(days),
    staleTime: 1000 * 60 * 2, // 2 minutes - consider stale quickly
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  });
}

/**
 * Hook to fetch sector ETF historical data for performance charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useSectorHistory(
  days: number = 365
): UseQueryResult<SectorHistoryResponse> {
  return useQuery({
    queryKey: ["market", "sector-history", days],
    queryFn: () => fetchSectorHistory(days),
    staleTime: 1000 * 60 * 2, // 2 minutes - consider stale quickly
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  });
}

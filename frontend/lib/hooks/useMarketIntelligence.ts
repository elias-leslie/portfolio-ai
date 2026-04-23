/**
 * React Query hooks for Market Intelligence API
 */

import { type UseQueryResult, useQuery } from '@tanstack/react-query'
import {
  type FearGreedHistoryResponse,
  fetchFearGreedHistory,
  fetchIndicatorHistory,
  fetchMarketEventsForChart,
  fetchMarketIntelligence,
  fetchMarketMovers,
  fetchMarketPredictionCommittee,
  fetchMarketPredictionHistory,
  fetchMarketPredictionReview,
  fetchMarketStatus,
  fetchNewsSentimentHistory,
  fetchSectorHistory,
  type IndicatorHistoryResponse,
  type MarketEventsChartResponse,
  type MarketIntelligenceResponse,
  type MarketMoversResponse,
  type MarketPredictionCommitteeResponse,
  type MarketPredictionHistoryResponse,
  type MarketPredictionSeatReviewResponse,
  type MarketStatusResponse,
  type NewsSentimentHistoryResponse,
  type SectorHistoryResponse,
} from '../api/market'

/**
 * Hook to fetch unified market intelligence
 * (narrative + dual scoring + sector rotation)
 */
export function useMarketIntelligence(): UseQueryResult<MarketIntelligenceResponse> {
  return useQuery({
    queryKey: ['market', 'intelligence'],
    queryFn: fetchMarketIntelligence,
    staleTime: 1000 * 60 * 15, // 15 minutes
    refetchInterval: 1000 * 60 * 15, // Refetch every 15 minutes
    refetchOnWindowFocus: false, // Data doesn't change that fast
  })
}

/**
 * Hook to fetch the latest market prediction committee snapshot for a selected trading-day window
 */
export function useMarketPredictionCommittee(
  windowDays: number = 3,
): UseQueryResult<MarketPredictionCommitteeResponse> {
  return useQuery({
    queryKey: ['market', 'prediction', 'committee', windowDays],
    queryFn: () => fetchMarketPredictionCommittee(windowDays),
    staleTime: 1000 * 60 * 10,
    refetchInterval: 1000 * 60 * 10,
    refetchOnWindowFocus: true,
  })
}

export function useMarketPredictionReview(
  windowDays: number = 3,
): UseQueryResult<MarketPredictionSeatReviewResponse> {
  return useQuery({
    queryKey: ['market', 'prediction', 'review', windowDays],
    queryFn: () => fetchMarketPredictionReview(windowDays),
    staleTime: 1000 * 60 * 10,
    refetchInterval: 1000 * 60 * 10,
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch market prediction history for a symbol/window pair
 */
export function useMarketPredictionHistory(
  symbol: string,
  windowDays: number = 3,
  limit: number = 30,
): UseQueryResult<MarketPredictionHistoryResponse> {
  return useQuery({
    queryKey: [
      'market',
      'prediction',
      'committee-history',
      symbol,
      windowDays,
      limit,
    ],
    queryFn: () => fetchMarketPredictionHistory(symbol, windowDays, limit),
    staleTime: 1000 * 60 * 10,
    refetchInterval: 1000 * 60 * 10,
    refetchOnWindowFocus: true,
    enabled: Boolean(symbol),
  })
}

/**
 * Hook to fetch Fear & Greed historical data for trend charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useFearGreedHistory(
  days: number = 365,
): UseQueryResult<FearGreedHistoryResponse> {
  return useQuery({
    queryKey: ['market', 'fear-greed-history', days],
    queryFn: () => fetchFearGreedHistory(days),
    staleTime: 1000 * 60 * 2, // 2 minutes - consider stale quickly
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  })
}

/**
 * Hook to fetch news sentiment historical data for trend charts
 * @param days - Number of days of history
 * @param granularity - 'daily' or 'hourly' (hourly useful for intraday view)
 */
export function useNewsSentimentHistory(
  days: number = 30,
  granularity: 'daily' | 'hourly' = 'daily',
): UseQueryResult<NewsSentimentHistoryResponse> {
  return useQuery({
    queryKey: ['market', 'news-sentiment-history', days, granularity],
    queryFn: () => fetchNewsSentimentHistory(days, granularity),
    staleTime: 1000 * 60 * 2, // 2 minutes
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch key indicator historical data for trend charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useIndicatorHistory(
  days: number = 365,
): UseQueryResult<IndicatorHistoryResponse> {
  return useQuery({
    queryKey: ['market', 'indicator-history', days],
    queryFn: () => fetchIndicatorHistory(days),
    staleTime: 1000 * 60 * 2, // 2 minutes - consider stale quickly
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  })
}

/**
 * Hook to fetch sector ETF historical data for performance charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useSectorHistory(
  days: number = 365,
): UseQueryResult<SectorHistoryResponse> {
  return useQuery({
    queryKey: ['market', 'sector-history', days],
    queryFn: () => fetchSectorHistory(days),
    staleTime: 1000 * 60 * 2, // 2 minutes - consider stale quickly
    refetchInterval: 1000 * 60 * 5, // Auto-refetch every 5 minutes
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  })
}

/**
 * Hook to fetch market movers (top gainers and losers)
 * Cached for 15 minutes (matches backend)
 */
export function useMarketMovers(
  count: number = 10,
): UseQueryResult<MarketMoversResponse> {
  return useQuery({
    queryKey: ['market', 'movers', count],
    queryFn: () => fetchMarketMovers(count),
    staleTime: 1000 * 60 * 15, // 15 minutes
    refetchInterval: 1000 * 60 * 15, // Auto-refetch every 15 minutes
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch market status (for staleness detection)
 * Cached for 1 minute (matches backend cache)
 */
export function useMarketStatus(): UseQueryResult<MarketStatusResponse> {
  return useQuery({
    queryKey: ['market', 'status'],
    queryFn: fetchMarketStatus,
    staleTime: 1000 * 60, // 1 minute
    refetchInterval: 1000 * 60, // Auto-refetch every minute
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch market events for chart overlays (FOMC, CPI, NFP)
 * Cached for 5 minutes - events don't change frequently
 */
export function useMarketEvents(
  days: number = 365,
): UseQueryResult<MarketEventsChartResponse> {
  return useQuery({
    queryKey: ['market', 'events', days],
    queryFn: () => fetchMarketEventsForChart(days),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnWindowFocus: false, // Events rarely change
  })
}

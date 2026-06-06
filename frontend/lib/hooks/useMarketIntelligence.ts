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
  fetchMarketStatus,
  fetchNewsSentimentHistory,
  fetchOvernightHistory,
  fetchSectorHistory,
  type IndicatorHistoryResponse,
  type MarketEventsChartResponse,
  type MarketIntelligenceResponse,
  type MarketMoversResponse,
  type MarketStatusResponse,
  type NewsSentimentHistoryResponse,
  type OvernightHistoryResponse,
  type SectorHistoryResponse,
} from '../api/market'
import { fetchPreferences } from '../api/preferences'

type PollMs = number | false

function useMarketPollMs(defaultSeconds: number = 30): PollMs {
  const { data: preferences } = useQuery({
    queryKey: ['preferences'],
    queryFn: fetchPreferences,
    staleTime: 1000 * 60 * 5,
  })
  if (preferences?.frontendPollInterval === 0) return false
  return (
    Math.max(10, preferences?.frontendPollInterval ?? defaultSeconds) * 1000
  )
}

function staleTimeForPoll(pollMs: PollMs) {
  return pollMs === false ? Number.POSITIVE_INFINITY : pollMs
}

/**
 * Hook to fetch unified market intelligence
 * (narrative + dual scoring + sector rotation)
 */
export function useMarketIntelligence(): UseQueryResult<MarketIntelligenceResponse> {
  const pollMs = useMarketPollMs()
  return useQuery({
    queryKey: ['market', 'intelligence'],
    queryFn: ({ signal }) => fetchMarketIntelligence({ signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
  })
}

/**
 * Hook to fetch Fear & Greed historical data for trend charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useFearGreedHistory(
  days: number = 365,
): UseQueryResult<FearGreedHistoryResponse> {
  const pollMs = useMarketPollMs(60)
  return useQuery({
    queryKey: ['market', 'fear-greed-history', days],
    queryFn: ({ signal }) => fetchFearGreedHistory(days, { signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
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
  const pollMs = useMarketPollMs(60)
  return useQuery({
    queryKey: ['market', 'news-sentiment-history', days, granularity],
    queryFn: ({ signal }) =>
      fetchNewsSentimentHistory(days, granularity, { signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
  })
}

/**
 * Hook to fetch key indicator historical data for trend charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useIndicatorHistory(
  days: number = 365,
): UseQueryResult<IndicatorHistoryResponse> {
  const pollMs = useMarketPollMs(60)
  return useQuery({
    queryKey: ['market', 'indicator-history', days],
    queryFn: ({ signal }) => fetchIndicatorHistory(days, { signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
  })
}

/**
 * Hook to fetch overnight-lean instrument history for the trend panel
 */
export function useOvernightHistory(
  days: number = 365,
): UseQueryResult<OvernightHistoryResponse> {
  const pollMs = useMarketPollMs(60)
  return useQuery({
    queryKey: ['market', 'overnight-history', days],
    queryFn: ({ signal }) => fetchOvernightHistory(days, { signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
  })
}

/**
 * Hook to fetch sector ETF historical data for performance charts
 * Auto-refreshes every 5 minutes to catch new data
 */
export function useSectorHistory(
  days: number = 365,
): UseQueryResult<SectorHistoryResponse> {
  const pollMs = useMarketPollMs(60)
  return useQuery({
    queryKey: ['market', 'sector-history', days],
    queryFn: ({ signal }) => fetchSectorHistory(days, { signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
  })
}

/**
 * Hook to fetch market movers (top gainers and losers)
 * Cached for 15 minutes (matches backend)
 */
export function useMarketMovers(
  count: number = 10,
): UseQueryResult<MarketMoversResponse> {
  const pollMs = useMarketPollMs(60)
  return useQuery({
    queryKey: ['market', 'movers', count],
    queryFn: ({ signal }) => fetchMarketMovers(count, { signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
  })
}

/**
 * Hook to fetch market status (for staleness detection)
 * Cached for 1 minute (matches backend cache)
 */
export function useMarketStatus(): UseQueryResult<MarketStatusResponse> {
  const pollMs = useMarketPollMs()
  return useQuery({
    queryKey: ['market', 'status'],
    queryFn: ({ signal }) => fetchMarketStatus({ signal }),
    staleTime: staleTimeForPoll(pollMs),
    refetchInterval: pollMs,
    refetchOnWindowFocus: pollMs !== false,
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
    queryFn: ({ signal }) => fetchMarketEventsForChart(days, { signal }),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnWindowFocus: false, // Events rarely change
  })
}

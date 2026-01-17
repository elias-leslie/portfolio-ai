/**
 * React Query hooks for Market API
 */

import { useQuery } from '@tanstack/react-query'
import { fetchMarketConditions, fetchPrices } from '../api/market'

/**
 * Hook to fetch current market conditions (S&P 500, VIX, 10Y yield, USD index)
 */
export function useMarketConditions() {
  return useQuery({
    queryKey: ['market', 'conditions'],
    queryFn: fetchMarketConditions,
    staleTime: 1000 * 60 * 2, // 2 minutes (reduced from 5min for fresher data)
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes (reduced from 15min)
  })
}

/**
 * Hook to fetch current prices for stock symbols
 */
export function usePrices(symbols: string[]) {
  return useQuery({
    queryKey: ['market', 'prices', symbols],
    queryFn: () => fetchPrices(symbols),
    enabled: symbols.length > 0,
    staleTime: 1000 * 60 * 1, // 1 minute
    refetchInterval: 1000 * 60 * 2, // Refetch every 2 minutes (reduced from 5min)
  })
}

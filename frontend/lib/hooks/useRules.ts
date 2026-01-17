/**
 * React Query hook for fetching trading rules
 */

import { useQuery } from '@tanstack/react-query'
import { fetchRules, type TradingRules } from '@/lib/api/rules'

export function useRules() {
  return useQuery<TradingRules>({
    queryKey: ['trading-rules'],
    queryFn: fetchRules,
    staleTime: 5 * 60 * 1000, // 5 minutes (matches backend cache TTL)
  })
}

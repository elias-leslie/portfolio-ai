import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import {
  fetchTradingRules,
  type TradingRulesResponse,
} from '@/lib/api/rules'

export function useTradingRules(options?: {
  enabled?: boolean
}): UseQueryResult<TradingRulesResponse> {
  return useQuery({
    queryKey: ['rules', 'trading'],
    queryFn: fetchTradingRules,
    staleTime: 1000 * 60 * 60,
    refetchOnWindowFocus: false,
    enabled: options?.enabled,
  })
}

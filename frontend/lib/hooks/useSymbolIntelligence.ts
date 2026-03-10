import { useQuery } from '@tanstack/react-query'
import { fetchSymbolIntelligence } from '@/lib/api/symbols'

export function useSymbolIntelligence(symbol: string) {
  return useQuery({
    queryKey: ['symbol-intelligence', symbol],
    queryFn: () => fetchSymbolIntelligence(symbol),
    enabled: symbol.trim().length > 0,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60 * 5,
  })
}

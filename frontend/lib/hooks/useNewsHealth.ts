import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { fetchNewsHealth, type NewsHealthResponse } from '@/lib/api/news'

export function useNewsHealth(
  refreshInterval: number = 60000,
): UseQueryResult<NewsHealthResponse> {
  return useQuery({
    queryKey: ['news', 'health'],
    queryFn: fetchNewsHealth,
    staleTime: refreshInterval,
    refetchInterval: refreshInterval,
    refetchOnWindowFocus: true,
  })
}

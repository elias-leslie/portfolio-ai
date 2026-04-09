import { type UseQueryResult, useQuery } from '@tanstack/react-query'
import {
  type DetailedHealthCheckResponse,
  fetchDetailedHealth,
} from '@/lib/api/health'

export function useDetailedHealth(): UseQueryResult<DetailedHealthCheckResponse> {
  return useQuery({
    queryKey: ['health', 'detailed'],
    queryFn: fetchDetailedHealth,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
    refetchOnWindowFocus: true,
  })
}

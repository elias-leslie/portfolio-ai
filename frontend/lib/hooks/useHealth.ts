import {
  type UseMutationResult,
  type UseQueryResult,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  type DetailedHealthCheckResponse,
  fetchDetailedHealth,
  fetchLiveFreshness,
  type LiveFreshnessResponse,
  refreshLiveFreshness,
} from '@/lib/api/health'
import { fetchPreferences } from '@/lib/api/preferences'

function pollIntervalMs(seconds?: number | null) {
  return Math.max(10, seconds ?? 30) * 1000
}

export function useDetailedHealth(): UseQueryResult<DetailedHealthCheckResponse> {
  return useQuery({
    queryKey: ['health', 'detailed'],
    queryFn: fetchDetailedHealth,
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
    refetchOnWindowFocus: true,
  })
}

export function useLiveFreshness(): UseQueryResult<LiveFreshnessResponse> {
  const { data: preferences } = useQuery({
    queryKey: ['preferences'],
    queryFn: fetchPreferences,
    staleTime: 1000 * 60 * 5,
  })
  const interval = pollIntervalMs(preferences?.frontendPollInterval)

  return useQuery({
    queryKey: ['health', 'freshness'],
    queryFn: fetchLiveFreshness,
    staleTime: interval,
    refetchInterval: interval,
    refetchOnWindowFocus: true,
  })
}

export function useRefreshAllFreshness(): UseMutationResult<
  LiveFreshnessResponse,
  Error,
  void
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: refreshLiveFreshness,
    onSuccess: () => {
      const keys = [
        ['health'],
        ['market'],
        ['home'],
        ['portfolio'],
        ['watchlist'],
        ['news'],
      ]
      keys.forEach((queryKey) => {
        void queryClient.invalidateQueries({
          queryKey,
          refetchType: 'active',
        })
      })
    },
  })
}

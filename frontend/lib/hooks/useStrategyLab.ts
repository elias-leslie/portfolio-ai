import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchStrategyLabDetail,
  fetchStrategyLabList,
  reviewStrategyLabSymbol,
  type StrategyLabDetail,
  type StrategyLabListResponse,
  type StrategyLabReviewError,
  type StrategyLabReviewSuccess,
} from '@/lib/api/strategy-lab'

export const strategyLabKeys = {
  all: ['strategy-lab'] as const,
  list: () => [...strategyLabKeys.all, 'list'] as const,
  detail: (symbol: string) =>
    [...strategyLabKeys.all, 'detail', symbol] as const,
}

export function useStrategyLabList() {
  return useQuery<StrategyLabListResponse, Error>({
    queryKey: strategyLabKeys.list(),
    queryFn: fetchStrategyLabList,
    staleTime: 0,
  })
}

export function useStrategyLabDetail(symbol: string | null) {
  return useQuery<StrategyLabDetail, Error>({
    queryKey: strategyLabKeys.detail(symbol ?? ''),
    queryFn: () => fetchStrategyLabDetail(symbol ?? ''),
    enabled: Boolean(symbol),
    staleTime: 0,
  })
}

export function useStrategyLabReview(symbol: string | null) {
  const queryClient = useQueryClient()
  return useMutation<
    StrategyLabReviewSuccess | StrategyLabReviewError,
    Error,
    void
  >({
    mutationFn: () => reviewStrategyLabSymbol(symbol ?? ''),
    onSuccess: async () => {
      if (symbol) {
        await queryClient.invalidateQueries({
          queryKey: strategyLabKeys.detail(symbol),
          refetchType: 'active',
        })
      }
    },
  })
}

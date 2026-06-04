import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { refreshToday } from '@/lib/api/home'

export function useTodayRefresh() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: refreshToday,
    onSuccess: (result) => {
      const keys = [
        ['signals'],
        ['market'],
        ['portfolio'],
        ['household'],
        ['home'],
      ]
      keys.forEach((queryKey) => {
        void queryClient.invalidateQueries({
          queryKey,
          refetchType: 'active',
        })
      })
      if (result.quoteSymbolsFailed.length > 0) {
        toast.error(
          `Today refreshed with ${result.quoteSymbolsFailed.length} quote issue${result.quoteSymbolsFailed.length === 1 ? '' : 's'}.`,
        )
      } else {
        toast.success('Today refreshed with current quotes.')
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Today refresh failed.',
      )
    },
  })
}

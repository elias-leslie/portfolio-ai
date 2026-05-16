import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  configureSnapTrade,
  createSnapTradeConnectionPortal,
  fetchSnapTradeStatus,
  type SnapTradeConfigurePayload,
  type SnapTradePortalPayload,
  syncSnapTrade,
} from '@/lib/api/snaptrade'

const SNAPTRADE_STALE_MS = 1000 * 60

function refreshSnapTrade(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['snaptrade'] }),
    queryClient.invalidateQueries({ queryKey: ['household'], exact: false }),
  ])
}

export function useSnapTradeStatus() {
  return useQuery({
    queryKey: ['snaptrade', 'status'],
    queryFn: fetchSnapTradeStatus,
    staleTime: SNAPTRADE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useConfigureSnapTrade() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SnapTradeConfigurePayload) =>
      configureSnapTrade(payload),
    onSuccess: async () => {
      await refreshSnapTrade(queryClient)
      toast.success('SnapTrade credentials saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to save SnapTrade credentials',
      )
    },
  })
}

export function useCreateSnapTradeConnectionPortal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SnapTradePortalPayload = {}) =>
      createSnapTradeConnectionPortal(payload),
    onSuccess: async () => {
      await refreshSnapTrade(queryClient)
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to create SnapTrade connection portal',
      )
    },
  })
}

export function useSyncSnapTrade() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: syncSnapTrade,
    onSuccess: async () => {
      await refreshSnapTrade(queryClient)
      toast.success('SnapTrade sync finished.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to sync SnapTrade data',
      )
    },
  })
}

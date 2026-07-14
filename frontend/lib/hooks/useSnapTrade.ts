import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  configureSnapTrade,
  createSnapTradeConnectionPortal,
  fetchSnapTradeOrders,
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

export function useSnapTradeOrders({
  accountId,
  enabled = true,
  limit = 50,
}: {
  accountId?: string | null
  enabled?: boolean
  limit?: number
} = {}) {
  return useQuery({
    queryKey: ['snaptrade', 'orders', accountId ?? 'all', limit],
    queryFn: () => fetchSnapTradeOrders({ accountId, limit }),
    enabled,
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
    onSuccess: async (result) => {
      await refreshSnapTrade(queryClient)
      const issueCount = Math.max(
        result.errorCount,
        result.errors.length,
        result.status === 'partial' ? 1 : 0,
      )
      if (result.status === 'partial' || result.errorCount > 0) {
        const firstError = result.errors[0]
        const surface =
          typeof firstError?.surface === 'string'
            ? firstError.surface.replaceAll('_', ' ')
            : null
        const message =
          typeof firstError?.errorMessage === 'string'
            ? firstError.errorMessage
            : null
        const remainingCount = Math.max(issueCount - 1, 0)
        const description = message
          ? `${surface ? `${surface}: ` : ''}${message}${remainingCount > 0 ? ` (+${remainingCount} more)` : ''}`
          : 'Some brokerage data could not be refreshed.'
        toast.warning(
          `SnapTrade sync finished with ${issueCount} issue${issueCount === 1 ? '' : 's'}.`,
          { description },
        )
        return
      }
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

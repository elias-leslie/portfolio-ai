import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  configurePlaid,
  createPlaidLinkToken,
  exchangePlaidPublicToken,
  fetchPlaidStatus,
  type PlaidConfigurePayload,
  plaidSyncIssues,
  removePlaidItem,
  syncPlaidItems,
} from '@/lib/api/plaid'

const PLAID_STALE_MS = 1000 * 60

function refreshPlaid(queryClient: ReturnType<typeof useQueryClient>) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['plaid'] }),
    queryClient.invalidateQueries({ queryKey: ['household'], exact: false }),
  ])
}

export function usePlaidStatus() {
  return useQuery({
    queryKey: ['plaid', 'status'],
    queryFn: fetchPlaidStatus,
    staleTime: PLAID_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useConfigurePlaid() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlaidConfigurePayload) => configurePlaid(payload),
    onSuccess: async () => {
      await refreshPlaid(queryClient)
      toast.success('Plaid credentials saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to save Plaid credentials',
      )
    },
  })
}

export function useCreatePlaidLinkToken() {
  return useMutation({
    mutationFn: createPlaidLinkToken,
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to create Plaid Link token',
      )
    },
  })
}

export function useExchangePlaidPublicToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: {
      publicToken: string
      metadata?: Record<string, unknown>
    }) => exchangePlaidPublicToken(payload),
    onSuccess: async (result) => {
      await refreshPlaid(queryClient)
      const issues = plaidSyncIssues(result.sync)
      if (issues) {
        toast.warning(
          `Plaid account linked; sync has ${issues.count} issue${issues.count === 1 ? '' : 's'}.`,
          { description: issues.description },
        )
      } else {
        toast.success('Plaid account linked.')
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to link Plaid account',
      )
    },
  })
}

export function useSyncPlaidItems() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { itemId?: string | null } = {}) =>
      syncPlaidItems(payload),
    onSuccess: async (result) => {
      await refreshPlaid(queryClient)
      const issues = plaidSyncIssues(result)
      if (issues) {
        toast.warning(
          `Plaid sync finished with ${issues.count} issue${issues.count === 1 ? '' : 's'}.`,
          { description: issues.description },
        )
      } else {
        toast.success('Plaid sync finished.')
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to sync Plaid data',
      )
    },
  })
}

export function useRemovePlaidItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (itemId: string) => removePlaidItem(itemId),
    onSuccess: async () => {
      await refreshPlaid(queryClient)
      toast.success('Plaid item removed.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to remove Plaid item',
      )
    },
  })
}

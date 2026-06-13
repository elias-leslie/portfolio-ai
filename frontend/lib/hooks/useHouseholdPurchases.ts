import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import type {
  HouseholdProductListParams,
  HouseholdPurchaseItemCategoryUpdate,
  HouseholdPurchaseItemProductAssignment,
} from '@/lib/api/household'
import {
  assignPurchaseItemProduct,
  categorizePurchaseItem,
  fetchHouseholdProductDetail,
  fetchHouseholdProducts,
  fetchPriceCheckStatus,
  fetchPurchaseItemReviewQueue,
  fetchTransactionPurchaseItems,
  mergeHouseholdProducts,
  triggerPriceCheck,
} from '@/lib/api/household/purchases'

const HOUSEHOLD_WORKSPACE_STALE_MS = 1000 * 60 * 5
const PRICE_CHECK_POLL_MS = 5000

async function refreshHouseholdQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await queryClient.resetQueries({
    queryKey: ['household'],
    exact: false,
  })
}

export function useHouseholdProducts(params?: HouseholdProductListParams) {
  return useQuery({
    queryKey: ['household', 'products', params ?? {}],
    queryFn: ({ signal }) => fetchHouseholdProducts(params, { signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  })
}

export function useHouseholdProductDetail(productId: string | null) {
  return useQuery({
    queryKey: ['household', 'product-detail', productId],
    queryFn: ({ signal }) =>
      fetchHouseholdProductDetail(productId as string, { signal }),
    enabled: productId !== null,
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useTransactionPurchaseItems(transactionId: string | null) {
  return useQuery({
    queryKey: ['household', 'transaction-purchase-items', transactionId],
    queryFn: ({ signal }) =>
      fetchTransactionPurchaseItems(transactionId as string, { signal }),
    enabled: transactionId !== null,
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function usePurchaseItemReviewQueue() {
  return useQuery({
    queryKey: ['household', 'purchase-item-review'],
    queryFn: ({ signal }) => fetchPurchaseItemReviewQueue({ signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useCategorizePurchaseItem() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      itemId,
      ...payload
    }: HouseholdPurchaseItemCategoryUpdate & { itemId: string }) =>
      categorizePurchaseItem(itemId, payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Item category saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to categorize item',
      )
    },
  })
}

export function useAssignPurchaseItemProduct() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      itemId,
      ...payload
    }: HouseholdPurchaseItemProductAssignment & { itemId: string }) =>
      assignPurchaseItemProduct(itemId, payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Product link updated.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to update product link',
      )
    },
  })
}

export function usePriceCheckStatus() {
  return useQuery({
    queryKey: ['household', 'price-check-status'],
    queryFn: ({ signal }) => fetchPriceCheckStatus({ signal }),
    staleTime: 0,
    refetchInterval: (query) => {
      const status = query.state.data?.latestRun?.status
      return status === 'queued' || status === 'running'
        ? PRICE_CHECK_POLL_MS
        : false
    },
    refetchOnWindowFocus: false,
  })
}

export function useTriggerPriceCheck() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => triggerPriceCheck(),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({
        queryKey: ['household', 'price-check-status'],
      })
      toast.success(
        result.alreadyRunning
          ? 'A price check is already running.'
          : 'Price check started.',
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to start price check',
      )
    },
  })
}

export function useMergeHouseholdProducts() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: {
      sourceProductId: string
      targetProductId: string
    }) => mergeHouseholdProducts(payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Products merged.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to merge products',
      )
    },
  })
}

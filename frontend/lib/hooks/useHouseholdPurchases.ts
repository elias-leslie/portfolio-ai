import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'
import { toast } from 'sonner'
import type {
  HouseholdProductListParams,
  HouseholdPurchaseItemCategoryUpdate,
  HouseholdPurchaseItemOwnerUpdate,
  HouseholdPurchaseItemProductAssignment,
  HouseholdShoppingListImportRequest,
  HouseholdShoppingListOptimizeRequest,
  HouseholdShoppingListRequest,
  HouseholdVendorProfileUpdate,
} from '@/lib/api/household'
import {
  assignPurchaseItemProduct,
  categorizePurchaseItem,
  createShoppingList,
  fetchHouseholdBuyGuide,
  fetchHouseholdProductDetail,
  fetchHouseholdProducts,
  fetchPriceCheckStatus,
  fetchPurchaseItemReviewQueue,
  fetchShoppingListSuggestions,
  fetchShoppingLists,
  fetchTransactionPurchaseItems,
  fetchVendorProfiles,
  importShoppingListItems,
  mergeHouseholdProducts,
  optimizeShoppingList,
  setPurchaseItemOwner,
  triggerPriceCheck,
  updateShoppingList,
  updateVendorProfiles,
} from '@/lib/api/household/purchases'

const HOUSEHOLD_WORKSPACE_STALE_MS = 1000 * 60 * 5
const PRICE_CHECK_POLL_MS = 5000
const PRICE_CHECK_TERMINAL_STATUSES = new Set([
  'completed',
  'completed_with_errors',
  'failed',
])

export function useHouseholdBuyGuide() {
  return useQuery({
    queryKey: ['household', 'buy-guide'],
    queryFn: ({ signal }) => fetchHouseholdBuyGuide({ signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

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

export function useSetPurchaseItemOwner() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      itemId,
      ...payload
    }: HouseholdPurchaseItemOwnerUpdate & { itemId: string }) =>
      setPurchaseItemOwner(itemId, payload),
    onSuccess: async () => {
      await refreshHouseholdQueries(queryClient)
      toast.success('Item owner saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to update item owner',
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
  const queryClient = useQueryClient()
  const lastInvalidatedRun = useRef<string | null>(null)
  const query = useQuery({
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

  useEffect(() => {
    const run = query.data?.latestRun
    if (!run || !PRICE_CHECK_TERMINAL_STATUSES.has(run.status)) return
    const invalidationKey = `${run.id}:${run.status}:${run.finishedAt ?? ''}`
    if (lastInvalidatedRun.current === invalidationKey) return
    lastInvalidatedRun.current = invalidationKey
    void queryClient.invalidateQueries({ queryKey: ['household', 'buy-guide'] })
    void queryClient.invalidateQueries({ queryKey: ['household', 'products'] })
    void queryClient.invalidateQueries({
      queryKey: ['household', 'shopping-lists'],
    })
  }, [
    query.data?.latestRun?.finishedAt,
    query.data?.latestRun?.id,
    query.data?.latestRun?.status,
    queryClient,
  ])

  return query
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

export function useShoppingLists() {
  return useQuery({
    queryKey: ['household', 'shopping-lists'],
    queryFn: ({ signal }) => fetchShoppingLists({ signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useShoppingListSuggestions(params?: {
  daysAhead?: number
  watchDays?: number
  limit?: number
}) {
  return useQuery({
    queryKey: ['household', 'shopping-list-suggestions', params],
    queryFn: ({ signal }) => fetchShoppingListSuggestions(params, { signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useCreateShoppingList() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdShoppingListRequest) =>
      createShoppingList(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['household', 'shopping-lists'],
      })
      toast.success('Shopping list created.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to create list',
      )
    },
  })
}

export function useUpdateShoppingList() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      listId,
      ...payload
    }: HouseholdShoppingListRequest & { listId: string }) =>
      updateShoppingList(listId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['household', 'shopping-lists'],
      })
      toast.success('Shopping list saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to save list',
      )
    },
  })
}

export function useImportShoppingListItems() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      listId,
      ...payload
    }: HouseholdShoppingListImportRequest & { listId: string }) =>
      importShoppingListItems(listId, payload),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({
        queryKey: ['household', 'shopping-lists'],
      })
      toast.success(
        `Imported ${result.parsedCount} item${
          result.parsedCount === 1 ? '' : 's'
        } (${result.matchedCount} matched).`,
      )
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to import items',
      )
    },
  })
}

export function useOptimizeShoppingList() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      listId,
      ...payload
    }: HouseholdShoppingListOptimizeRequest & { listId: string }) =>
      optimizeShoppingList(listId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['household', 'shopping-lists'],
      })
      toast.success('Shopping list optimized.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : 'Failed to optimize list',
      )
    },
  })
}

export function useVendorProfiles() {
  return useQuery({
    queryKey: ['household', 'vendor-profiles'],
    queryFn: ({ signal }) => fetchVendorProfiles({ signal }),
    staleTime: HOUSEHOLD_WORKSPACE_STALE_MS,
    refetchOnWindowFocus: false,
  })
}

export function useUpdateVendorProfiles() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: HouseholdVendorProfileUpdate) =>
      updateVendorProfiles(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ['household', 'vendor-profiles'],
      })
      await queryClient.invalidateQueries({
        queryKey: ['household', 'shopping-lists'],
      })
      toast.success('Vendor profile saved.')
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to save vendor profile',
      )
    },
  })
}

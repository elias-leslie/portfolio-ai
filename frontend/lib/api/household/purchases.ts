import { get, post, put } from '../client'
import type {
  HouseholdBuyGuide,
  HouseholdPriceCheckStatus,
  HouseholdPriceCheckTriggerResponse,
  HouseholdProductDetail,
  HouseholdProductList,
  HouseholdProductListParams,
  HouseholdPurchaseItem,
  HouseholdPurchaseItemCategoryUpdate,
  HouseholdPurchaseItemOwnerUpdate,
  HouseholdPurchaseItemProductAssignment,
  HouseholdPurchaseItemReviewQueue,
  HouseholdShoppingList,
  HouseholdShoppingListImportRequest,
  HouseholdShoppingListImportResponse,
  HouseholdShoppingListOptimizeRequest,
  HouseholdShoppingListRequest,
  HouseholdShoppingListSuggestions,
  HouseholdShoppingListsResponse,
  HouseholdVendorProfileList,
  HouseholdVendorProfileUpdate,
} from './types'

export async function fetchHouseholdBuyGuide(
  options: RequestInit = {},
): Promise<HouseholdBuyGuide> {
  return get<HouseholdBuyGuide>('/api/household/buy-guide', options)
}

export async function fetchHouseholdProducts(
  params?: HouseholdProductListParams,
  options: RequestInit = {},
): Promise<HouseholdProductList> {
  const search = new URLSearchParams()
  if (params?.search) search.set('search', params.search)
  if (params?.sort) search.set('sort', params.sort)
  if (params?.sortDir) search.set('sort_dir', params.sortDir)
  if (params?.scope) search.set('scope', params.scope)
  if (params?.limit != null) search.set('limit', String(params.limit))
  if (params?.offset != null) search.set('offset', String(params.offset))
  const query = search.toString()
  return get<HouseholdProductList>(
    query ? `/api/household/products?${query}` : '/api/household/products',
    options,
  )
}

export async function fetchHouseholdProductDetail(
  productId: string,
  options: RequestInit = {},
): Promise<HouseholdProductDetail> {
  return get<HouseholdProductDetail>(
    `/api/household/products/${productId}`,
    options,
  )
}

export async function mergeHouseholdProducts(payload: {
  sourceProductId: string
  targetProductId: string
}): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>('/api/household/products/merge', payload)
}

export async function fetchTransactionPurchaseItems(
  transactionId: string,
  options: RequestInit = {},
): Promise<HouseholdPurchaseItem[]> {
  return get<HouseholdPurchaseItem[]>(
    `/api/household/transactions/${transactionId}/purchase-items`,
    options,
  )
}

export async function fetchPurchaseItemReviewQueue(
  options: RequestInit = {},
): Promise<HouseholdPurchaseItemReviewQueue> {
  return get<HouseholdPurchaseItemReviewQueue>(
    '/api/household/purchase-items/review',
    options,
  )
}

export async function categorizePurchaseItem(
  itemId: string,
  payload: HouseholdPurchaseItemCategoryUpdate,
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(
    `/api/household/purchase-items/${itemId}/categorize`,
    payload,
  )
}

export async function setPurchaseItemOwner(
  itemId: string,
  payload: HouseholdPurchaseItemOwnerUpdate,
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(
    `/api/household/purchase-items/${itemId}/owner`,
    payload,
  )
}

export async function assignPurchaseItemProduct(
  itemId: string,
  payload: HouseholdPurchaseItemProductAssignment,
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(
    `/api/household/purchase-items/${itemId}/product`,
    payload,
  )
}

export async function fetchPriceCheckStatus(
  options: RequestInit = {},
): Promise<HouseholdPriceCheckStatus> {
  return get<HouseholdPriceCheckStatus>(
    '/api/household/price-checks/status',
    options,
  )
}

export async function triggerPriceCheck(): Promise<HouseholdPriceCheckTriggerResponse> {
  return post<HouseholdPriceCheckTriggerResponse>(
    '/api/household/price-checks/run',
    {},
  )
}

export async function fetchShoppingLists(
  options: RequestInit = {},
): Promise<HouseholdShoppingListsResponse> {
  return get<HouseholdShoppingListsResponse>(
    '/api/household/shopping-lists',
    options,
  )
}

export async function fetchShoppingListSuggestions(
  params: { daysAhead?: number; watchDays?: number; limit?: number } = {},
  options: RequestInit = {},
): Promise<HouseholdShoppingListSuggestions> {
  const search = new URLSearchParams()
  if (params.daysAhead != null) {
    search.set('days_ahead', String(params.daysAhead))
  }
  if (params.watchDays != null) {
    search.set('watch_days', String(params.watchDays))
  }
  if (params.limit != null) search.set('limit', String(params.limit))
  const query = search.toString()
  return get<HouseholdShoppingListSuggestions>(
    query
      ? `/api/household/shopping-lists/suggestions?${query}`
      : '/api/household/shopping-lists/suggestions',
    options,
  )
}

export async function createShoppingList(
  payload: HouseholdShoppingListRequest,
): Promise<HouseholdShoppingList> {
  return post<HouseholdShoppingList>('/api/household/shopping-lists', payload)
}

export async function updateShoppingList(
  listId: string,
  payload: HouseholdShoppingListRequest,
): Promise<HouseholdShoppingList> {
  return put<HouseholdShoppingList>(
    `/api/household/shopping-lists/${listId}`,
    payload,
  )
}

export async function importShoppingListItems(
  listId: string,
  payload: HouseholdShoppingListImportRequest,
): Promise<HouseholdShoppingListImportResponse> {
  return post<HouseholdShoppingListImportResponse>(
    `/api/household/shopping-lists/${listId}/import`,
    payload,
  )
}

export async function optimizeShoppingList(
  listId: string,
  payload: HouseholdShoppingListOptimizeRequest = {},
): Promise<HouseholdShoppingList> {
  return post<HouseholdShoppingList>(
    `/api/household/shopping-lists/${listId}/optimize`,
    payload,
  )
}

export async function fetchVendorProfiles(
  options: RequestInit = {},
): Promise<HouseholdVendorProfileList> {
  return get<HouseholdVendorProfileList>(
    '/api/household/vendor-profiles',
    options,
  )
}

export async function updateVendorProfiles(
  payload: HouseholdVendorProfileUpdate,
): Promise<HouseholdVendorProfileList> {
  return put<HouseholdVendorProfileList>(
    '/api/household/vendor-profiles',
    payload,
  )
}

import { del, get, post } from './client'

export interface PlaidStatusItem {
  itemId: string
  institutionName: string | null
  status: string
  lastSuccessfulSyncAt: string | null
  lastError: string | null
}

export interface PlaidStatus {
  configured: boolean
  encryptionReady: boolean
  environment: string | null
  products: string[]
  countryCodes: string[]
  redirectUri: string | null
  itemCount: number
  accountCount: number
  transactionCount: number
  lastSuccessfulSyncAt: string | null
  items: PlaidStatusItem[]
}

export interface PlaidConfigurePayload {
  clientId: string
  secret: string
  environment: string
  products: string[]
  countryCodes: string[]
  redirectUri?: string | null
}

export interface PlaidLinkTokenResponse {
  linkToken: string
  expiration?: string
  requestId?: string
}

export interface PlaidSyncResult {
  itemCount: number
  accountCount: number
  transactionAddedCount: number
  transactionModifiedCount: number
  transactionRemovedCount: number
  errors: Array<Record<string, unknown>>
}

export interface PlaidExchangeResult {
  itemId: string
  institutionName: string | null
  sync: PlaidSyncResult
}

export function fetchPlaidStatus(): Promise<PlaidStatus> {
  return get<PlaidStatus>('/api/plaid/status')
}

export function configurePlaid(
  payload: PlaidConfigurePayload,
): Promise<PlaidStatus> {
  return post<PlaidStatus>('/api/plaid/configure', payload)
}

export function createPlaidLinkToken(): Promise<PlaidLinkTokenResponse> {
  return post<PlaidLinkTokenResponse>('/api/plaid/link-token')
}

export function exchangePlaidPublicToken(payload: {
  publicToken: string
  metadata?: Record<string, unknown>
}): Promise<PlaidExchangeResult> {
  return post<PlaidExchangeResult>('/api/plaid/exchange-public-token', payload)
}

export function syncPlaidItems(
  payload: { itemId?: string | null } = {},
): Promise<PlaidSyncResult> {
  return post<PlaidSyncResult>('/api/plaid/sync', payload)
}

export function removePlaidItem(itemId: string): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/plaid/items/${itemId}`)
}

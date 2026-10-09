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
  clientIdConfigured: boolean
  secretConfigured: boolean
  configurationUpdatedAt: string | null
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
  clientId?: string
  secret?: string
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
  skipped?: Array<Record<string, unknown>>
}

export interface PlaidExchangeResult {
  itemId: string
  institutionName: string | null
  sync: PlaidSyncResult
}

export function plaidSyncIssues(result: unknown): {
  count: number
  description: string
} | null {
  if (
    typeof result !== 'object' ||
    result === null ||
    !('errors' in result) ||
    !Array.isArray(result.errors)
  ) {
    return { count: 1, description: 'Sync status is unavailable.' }
  }
  if (result.errors.length === 0) {
    const skipped =
      'skipped' in result && Array.isArray(result.skipped)
        ? result.skipped.length
        : 0
    if (skipped === 0) return null
    return {
      count: skipped,
      description: `A sync is already running for ${skipped === 1 ? 'this connection' : `${skipped} connections`}; its results will appear when it finishes.`,
    }
  }
  const first: unknown = result.errors[0]
  const detail =
    typeof first === 'object' && first !== null
      ? ['errorMessage', 'error_message', 'detail']
          .map((key) => (first as Record<string, unknown>)[key])
          .find(
            (value): value is string =>
              typeof value === 'string' && value.trim().length > 0,
          )
      : undefined
  return {
    count: result.errors.length,
    description: `${detail ?? 'Some Plaid data could not be refreshed.'}${
      result.errors.length > 1 ? ` (+${result.errors.length - 1} more)` : ''
    }`,
  }
}

export function fetchPlaidStatus(): Promise<PlaidStatus> {
  return get<PlaidStatus>('/api/plaid/status')
}

export function configurePlaid(
  payload: PlaidConfigurePayload,
): Promise<PlaidStatus> {
  return post<PlaidStatus>('/api/plaid/configure', payload)
}

export function createPlaidLinkToken(
  payload: { itemId?: string | null } = {},
): Promise<PlaidLinkTokenResponse> {
  // With an itemId, Link reopens the account picker for a connection that
  // already exists -- the only way to add a card at an institution the
  // household is already connected to.
  return post<PlaidLinkTokenResponse>('/api/plaid/link-token', {
    item_id: payload.itemId ?? null,
  })
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

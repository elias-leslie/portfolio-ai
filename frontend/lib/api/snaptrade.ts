import { get, post } from './client'

export interface SnapTradeConnection {
  authorizationId: string
  brokerageName: string | null
  brokerageSlug: string | null
  connectionType: string
  disabled: boolean
  lastSyncedAt: string | null
}

export interface SnapTradeAccount {
  accountId: string
  name: string
  institutionName: string | null
  accountMask: string | null
  portfolioAccountType: string
  balance: number | null
  marketValue: number | null
  valuationSource: 'live' | 'broker' | 'unknown'
  quoteAsOf: string | null
  cashBalance: number | null
  currency: string | null
  lastSyncedAt: string | null
}

export interface SnapTradeOrder {
  accountId: string
  accountName: string | null
  institutionName: string | null
  accountMask: string | null
  brokerageOrderId: string
  status: string | null
  action: string | null
  symbol: string | null
  rawSymbol: string | null
  filledQuantity: number | null
  executionPrice: number | null
  orderType: string | null
  timeInForce: string | null
  timePlaced: string | null
  timeUpdated: string | null
  timeExecuted: string | null
  currency: string | null
  lastSyncedAt: string | null
}

export interface SnapTradeOrdersResponse {
  orders: SnapTradeOrder[]
}

export interface SnapTradeStatus {
  configured: boolean
  clientIdConfigured: boolean
  consumerKeyConfigured: boolean
  configurationUpdatedAt: string | null
  encryptionReady: boolean
  accessMode: 'read_only'
  defaultBroker: string
  redirectUri: string | null
  userRegistered: boolean
  connectionCount: number
  accountCount: number
  sourceAccountCount: number
  positionCount: number
  activityCount: number
  orderCount: number
  lastSuccessfulSyncAt: string | null
  lastError: string | null
  connections: SnapTradeConnection[]
  accounts: SnapTradeAccount[]
}

export interface SnapTradeConfigurePayload {
  clientId?: string
  consumerKey?: string
  redirectUri?: string | null
  defaultBroker?: string | null
}

export interface SnapTradePortalPayload {
  broker?: string | null
}

export interface SnapTradePortalResponse {
  portalUrl: string
  sessionId?: string | null
  broker?: string | null
  accessMode: 'read_only'
  expiresInMinutes: number
}

export interface SnapTradeSyncResult {
  status: 'success' | 'partial'
  connectionCount: number
  accountCount: number
  positionCount: number
  activityCount: number
  orderCount: number
  portfolioAccountCount: number
  portfolioPositionCount: number
  errorCount: number
  errors: Array<Record<string, unknown>>
}

export function fetchSnapTradeStatus(): Promise<SnapTradeStatus> {
  return get<SnapTradeStatus>('/api/snaptrade/status')
}

export function fetchSnapTradeOrders({
  accountId,
  limit = 50,
}: {
  accountId?: string | null
  limit?: number
} = {}): Promise<SnapTradeOrdersResponse> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (accountId) {
    params.set('account_id', accountId)
  }
  return get<SnapTradeOrdersResponse>(`/api/snaptrade/orders?${params}`)
}

export function configureSnapTrade(
  payload: SnapTradeConfigurePayload,
): Promise<SnapTradeStatus> {
  return post<SnapTradeStatus>('/api/snaptrade/configure', payload)
}

export function createSnapTradeConnectionPortal(
  payload: SnapTradePortalPayload = {},
): Promise<SnapTradePortalResponse> {
  return post<SnapTradePortalResponse>(
    '/api/snaptrade/connection-portal',
    payload,
  )
}

export function syncSnapTrade(): Promise<SnapTradeSyncResult> {
  return post<SnapTradeSyncResult>('/api/snaptrade/sync')
}

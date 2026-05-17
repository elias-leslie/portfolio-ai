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
  cashBalance: number | null
  currency: string | null
  lastSyncedAt: string | null
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
  positionCount: number
  activityCount: number
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
  connectionCount: number
  accountCount: number
  positionCount: number
  activityCount: number
  portfolioAccountCount: number
  portfolioPositionCount: number
  errors: Array<Record<string, unknown>>
}

export function fetchSnapTradeStatus(): Promise<SnapTradeStatus> {
  return get<SnapTradeStatus>('/api/snaptrade/status')
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

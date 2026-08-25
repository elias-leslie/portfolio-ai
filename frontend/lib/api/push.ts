/**
 * The household push channel (plan §7 3.6, D11).
 *
 * A subscription is a device, so everything here is per-browser: this phone
 * subscribes, this phone says whose it is, this phone can turn it off. The
 * application server key is public by design — a browser cannot subscribe
 * without it — and the private half never leaves the backend.
 */
import { del, get, post } from './client'

export interface PushSubscriptionView {
  id: string
  householdMemberId: string | null
  memberName: string | null
  deviceLabel: string | null
  createdAt: string | null
  lastSuccessAt: string | null
  lastFailureAt: string | null
  lastError: string | null
}

export interface PushRecipient {
  id: string
  name: string
}

export interface PushSubscriptionList {
  enabled: boolean
  publicKey: string
  /** The adults a device can be registered to — the girls are capture-only. */
  recipients: PushRecipient[]
  subscriptions: PushSubscriptionView[]
}

export interface PushRegistration {
  endpoint: string
  keys: { encryptionKey: string; authSecret: string }
  householdMemberId: string | null
  deviceLabel: string | null
  userAgent: string | null
}

export interface PushDelivery {
  delivered: number
  failed: number
  expired: number
}

export function fetchPushSubscriptions(): Promise<PushSubscriptionList> {
  return get<PushSubscriptionList>('/api/household/push/subscriptions')
}

export function registerPushSubscription(
  registration: PushRegistration,
): Promise<PushSubscriptionView> {
  return post<PushSubscriptionView>(
    '/api/household/push/subscriptions',
    registration,
  )
}

export function deletePushSubscription(
  subscriptionId: string,
): Promise<{ removed: boolean }> {
  return del<{ removed: boolean }>(
    `/api/household/push/subscriptions/${subscriptionId}`,
  )
}

/** Drop the row for an endpoint this device holds but has no row id for. */
export function unsubscribePushEndpoint(
  endpoint: string,
): Promise<{ removed: boolean }> {
  return post<{ removed: boolean }>('/api/household/push/unsubscribe', {
    endpoint,
  })
}

export function sendTestPush(
  subscriptionId?: string | null,
): Promise<PushDelivery> {
  return post<PushDelivery>('/api/household/push/test', {
    subscriptionId: subscriptionId ?? null,
  })
}

/**
 * The device half of web push (plan §7 3.6).
 *
 * Everything here is about *this* browser: whether it can receive push at all,
 * whether it already has a subscription, and how to start or end one. The
 * server is told the result; it never drives this side, because only the
 * browser can mint an endpoint and only the person holding the phone can grant
 * permission.
 */
import type { PushRegistration } from '@/lib/api/push'

export type PushSupport = 'supported' | 'unsupported' | 'insecure-context'

export type PushPermission = 'default' | 'granted' | 'denied'

/**
 * Push needs a secure context, so an http:// origin that is not localhost is
 * reported apart from an old browser: one is a deployment fact the household
 * can fix, the other is not.
 */
export function pushSupport(): PushSupport {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') {
    return 'unsupported'
  }
  if (
    !('serviceWorker' in navigator) ||
    !('PushManager' in window) ||
    !('Notification' in window)
  ) {
    return window.isSecureContext === false ? 'insecure-context' : 'unsupported'
  }
  return window.isSecureContext === false ? 'insecure-context' : 'supported'
}

export function pushPermission(): PushPermission {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'default'
  }
  return Notification.permission as PushPermission
}

/**
 * The VAPID public key travels as base64url text and `subscribe()` wants raw
 * bytes, so it is decoded here rather than shipped pre-encoded — the same key
 * the backend hands out is the one the browser signs against.
 */
export function urlBase64ToUint8Array(
  base64String: string,
): Uint8Array<ArrayBuffer> {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  // Backed by a plain ArrayBuffer, not a SharedArrayBuffer: `subscribe()` only
  // accepts the former as an application server key.
  const output = new Uint8Array(new ArrayBuffer(raw.length))
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i)
  }
  return output
}

/**
 * A name a person can recognise in a device list.
 *
 * Android puts the phone's own model in the user-agent build token — "Pixel 7
 * Pro", "SM-S908U" — which is the only string here that tells Elias's handset
 * from Mariana's. When there is no model token the browser name is at least
 * honest about which browser subscribed.
 */
export function deviceLabelFrom(userAgent: string): string {
  const android = /Android\s+[\d.]+;\s*([^;)]+)/.exec(userAgent)
  const model = android?.[1]?.replace(/\bBuild\/.*$/, '').trim()
  if (model && model.toLowerCase() !== 'k') {
    return model
  }
  if (/iPhone|iPad/.test(userAgent)) {
    return /iPad/.test(userAgent) ? 'iPad' : 'iPhone'
  }
  if (/Edg\//.test(userAgent)) return 'Edge on desktop'
  if (/Firefox\//.test(userAgent)) return 'Firefox on desktop'
  if (/Chrome\//.test(userAgent)) return 'Chrome on desktop'
  if (/Safari\//.test(userAgent)) return 'Safari on desktop'
  return 'This device'
}

async function readyRegistration(): Promise<ServiceWorkerRegistration> {
  return navigator.serviceWorker.ready
}

/** The endpoint this browser already holds, if it has one. */
export async function currentEndpoint(): Promise<string | null> {
  if (pushSupport() !== 'supported') return null
  const registration = await readyRegistration()
  const existing = await registration.pushManager.getSubscription()
  return existing?.endpoint ?? null
}

/**
 * Ask for permission, subscribe, and return what the server needs to store.
 *
 * An existing subscription is reused rather than replaced: the endpoint is the
 * device's identity, and churning it would orphan the row the backend already
 * pushes to.
 */
export async function subscribeThisDevice(
  publicKey: string,
  householdMemberId: string | null,
): Promise<PushRegistration> {
  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    throw new Error(
      permission === 'denied'
        ? 'This device blocked notifications. Allow them in the browser site settings, then try again.'
        : 'Notification permission was dismissed.',
    )
  }
  const registration = await readyRegistration()
  const subscription =
    (await registration.pushManager.getSubscription()) ??
    (await registration.pushManager.subscribe({
      // Web push has no silent delivery on Chrome: every push must show a
      // notification, which is what the household asked for anyway.
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    }))

  const json = subscription.toJSON()
  const keys = json.keys ?? {}
  if (!json.endpoint || !keys.p256dh || !keys.auth) {
    throw new Error('The browser returned an incomplete push subscription.')
  }
  return {
    endpoint: json.endpoint,
    keys: { encryptionKey: keys.p256dh, authSecret: keys.auth },
    householdMemberId,
    deviceLabel: deviceLabelFrom(navigator.userAgent),
    userAgent: navigator.userAgent,
  }
}

/** End this browser's subscription. Returns the endpoint that was dropped. */
export async function unsubscribeThisDevice(): Promise<string | null> {
  if (pushSupport() !== 'supported') return null
  const registration = await readyRegistration()
  const subscription = await registration.pushManager.getSubscription()
  if (!subscription) return null
  const { endpoint } = subscription
  await subscription.unsubscribe()
  return endpoint
}

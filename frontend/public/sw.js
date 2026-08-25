// fallow-ignore-file unused-file
// Registered by frontend/app/layout.tsx via a static service-worker script string.
const CACHE_NAME = 'portfolio-ai-pwa-v3'
const SHELL_ASSETS = [
  '/manifest.json',
  '/favicon.ico',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith('portfolio-ai-') && key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

// --- Push (plan §7 3.6, D11) ------------------------------------------------
// The alert channel. The backend encrypts {title, body, severity, url, tag} to
// this device's own key, so the payload arrives here and nowhere else.

// The Budget tab's route value is 'spending' -- the label and the value differ.
const PUSH_FALLBACK_URL = '/money?tab=spending'

function pushPayload(event) {
  // A push with no data is a real case: a service can wake a worker without
  // one, and Android will show its own generic notice if we show nothing. So
  // there is always a notification, even when there is nothing to say.
  if (!event.data) {
    return { title: 'Portfolio AI', body: 'Open the plan for the latest.' }
  }
  try {
    return event.data.json()
  } catch (error) {
    return { title: 'Portfolio AI', body: event.data.text() }
  }
}

self.addEventListener('push', (event) => {
  const payload = pushPayload(event)
  const url = payload.url || PUSH_FALLBACK_URL
  event.waitUntil(
    self.registration.showNotification(payload.title || 'Portfolio AI', {
      body: payload.body || '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      // Same tag as the alert's dedupe marker: a repeat of one crossing
      // replaces its own tray entry instead of stacking under it.
      tag: payload.tag || 'portfolio-ai-alert',
      renotify: true,
      // Money findings are what the household asked to be interrupted for;
      // anything softer would be a notification nobody sees until later.
      requireInteraction: payload.severity === 'critical',
      data: { url },
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = (event.notification.data && event.notification.data.url) || PUSH_FALLBACK_URL
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Reuse a tab that is already on this app rather than opening a second
        // one: the household reads one screen, not a stack of them.
        for (const client of clientList) {
          if (new URL(client.url).origin === self.location.origin) {
            return client.focus().then(() => {
              if ('navigate' in client) {
                return client.navigate(target)
              }
              return client
            })
          }
        }
        return self.clients.openWindow(target)
      }),
  )
})

self.addEventListener('pushsubscriptionchange', (event) => {
  // The browser rotated this device's endpoint. Tell the server so the old row
  // stops being pushed to; the app re-subscribes on its next load.
  const oldEndpoint = event.oldSubscription && event.oldSubscription.endpoint
  if (!oldEndpoint) {
    return
  }
  event.waitUntil(
    fetch('/api/household/push/unsubscribe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint: oldEndpoint }),
    }).catch(() => undefined),
  )
})

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') {
    return
  }

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) {
    return
  }

  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/health') ||
    url.pathname.startsWith('/ws/')
  ) {
    event.respondWith(fetch(request))
    return
  }

  if (SHELL_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request)),
    )
    return
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (
          response.ok &&
          (request.destination === 'script' ||
            request.destination === 'style' ||
            request.destination === 'font' ||
            url.pathname.startsWith('/_next/static/'))
        ) {
          const copy = response.clone()
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy))
        }
        return response
      })
      .catch(() =>
        caches.match(request).then((cached) => cached || Response.error()),
      ),
  )
})

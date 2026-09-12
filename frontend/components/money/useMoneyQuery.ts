'use client'

import { useCallback, useSyncExternalStore } from 'react'

function subscribe(callback: () => void) {
  window.addEventListener('popstate', callback)
  window.addEventListener('locationchange', callback)
  return () => {
    window.removeEventListener('popstate', callback)
    window.removeEventListener('locationchange', callback)
  }
}

export function setMoneyQuery(
  values: Record<string, string | null>,
  replace = false,
) {
  const url = new URL(window.location.href)
  for (const [key, value] of Object.entries(values)) {
    if (value == null || value === '') url.searchParams.delete(key)
    else url.searchParams.set(key, value)
  }
  if (url.href === window.location.href) return
  window.history[replace ? 'replaceState' : 'pushState'](
    window.history.state,
    '',
    url,
  )
  window.dispatchEvent(new Event('locationchange'))
}

export function useMoneyQuery<T extends string = string>(
  key: string,
  fallback: string,
  allowed?: readonly T[],
) {
  const read = useCallback(() => {
    const raw = new URLSearchParams(window.location.search).get(key)
    return raw != null && (!allowed || allowed.includes(raw as T))
      ? (raw as T)
      : (fallback as T)
  }, [key, fallback, allowed])
  const value = useSyncExternalStore(subscribe, read, () => fallback as T)
  const set = useCallback(
    (next: T) =>
      setMoneyQuery({
        [key]: next === fallback ? null : next,
        ...(key.startsWith('ledger') && key !== 'ledgerPage'
          ? { ledgerPage: null }
          : {}),
      }),
    [key, fallback],
  )
  return [value, set] as const
}

export function reviewLedgerHref(month: string, category?: string) {
  const params = new URLSearchParams({
    tab: 'ledger',
    month,
    ledgerKind: 'transactions',
    ledgerStatus: 'all',
    ledgerInclusion: 'included',
  })
  if (category) params.set('ledgerCategory', category)
  return `/money?${params}`
}

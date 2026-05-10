'use client'

import { useEffect, useState } from 'react'

import { formatRelativeTime } from '@/lib/utils'

export interface RelativeTimeProps {
  value: string | null | undefined
  fallback?: string
  /** Refresh cadence in ms once mounted. Defaults to 60s — matches the minute-level granularity of the relative format. */
  refreshMs?: number
}

/**
 * Hydration-safe relative time label.
 *
 * Renders a stable "—" placeholder on the server and on first client paint,
 * then swaps to the live relative label inside an effect. This avoids the
 * server/client clock-skew mismatch that triggers React #418.
 */
export function RelativeTime({
  value,
  fallback,
  refreshMs = 60_000,
}: RelativeTimeProps) {
  const [label, setLabel] = useState<string | null>(null)

  useEffect(() => {
    if (!value) {
      setLabel(fallback ?? formatRelativeTime(value))
      return
    }
    const update = () => setLabel(formatRelativeTime(value))
    update()
    const timer = setInterval(update, refreshMs)
    return () => clearInterval(timer)
  }, [value, fallback, refreshMs])

  return <>{label ?? '—'}</>
}

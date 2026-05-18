'use client'

import { Sparkles, X } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'

const STORAGE_KEY = 'signals:today-next-banner-dismissed'

export function TodayNextBanner() {
  const [dismissed, setDismissed] = useState(true) // hide on first paint to avoid flash

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY)
      setDismissed(stored === 'true')
    } catch {
      setDismissed(false)
    }
  }, [])

  const handleDismiss = () => {
    setDismissed(true)
    try {
      window.localStorage.setItem(STORAGE_KEY, 'true')
    } catch {
      // ignore
    }
  }

  if (dismissed) return null

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-[#00f5ff]/30 bg-gradient-to-r from-[#00f5ff]/5 via-transparent to-[#a855f7]/5 px-4 py-3 text-sm">
      <Sparkles className="h-4 w-4 text-[#00f5ff]" />
      <span className="flex-1 text-text">
        New 3-tier signal stack is live —
        <Link
          href="/today-next"
          className="ml-1 font-semibold text-primary hover:underline"
        >
          Try Today-next (signals preview) →
        </Link>
      </span>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Dismiss banner"
        className="rounded-full p-1 text-text-muted transition-colors hover:bg-surface/60 hover:text-text"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}

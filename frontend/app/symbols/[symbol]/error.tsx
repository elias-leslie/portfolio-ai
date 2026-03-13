'use client'

import { useEffect } from 'react'

export default function SymbolError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Symbol page error:', error)
  }, [error])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-xl font-semibold text-text">
        Failed to load symbol data
      </h2>
      <p className="max-w-md text-center text-sm text-text-muted">
        Could not load the requested symbol. The data source may be temporarily
        unavailable.
      </p>
      <button
        type="button"
        onClick={reset}
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Retry
      </button>
    </div>
  )
}

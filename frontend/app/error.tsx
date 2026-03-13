'use client'

import { useEffect } from 'react'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Unhandled error:', error)
  }, [error])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-xl font-semibold text-text">Something went wrong</h2>
      <p className="max-w-md text-center text-sm text-text-muted">
        An unexpected error occurred. Try refreshing, or click the button below
        to recover.
      </p>
      {error.digest ? (
        <p className="text-xs text-text-muted">Error ID: {error.digest}</p>
      ) : null}
      <button
        type="button"
        onClick={reset}
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        Try again
      </button>
    </div>
  )
}

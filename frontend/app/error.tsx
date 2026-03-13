'use client'

import { AlertTriangle } from 'lucide-react'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'

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
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 p-8">
      <div className="rounded-full bg-loss/10 p-4">
        <AlertTriangle className="h-8 w-8 text-loss" />
      </div>
      <div className="text-center space-y-2">
        <h2 className="text-xl font-semibold text-text">Something went wrong</h2>
        <p className="max-w-md text-sm text-text-muted leading-relaxed">
          An unexpected error occurred. Try refreshing, or click the button below
          to recover.
        </p>
        {error.digest ? (
          <p className="text-xs text-text-muted/60">Error ID: {error.digest}</p>
        ) : null}
      </div>
      <Button type="button" onClick={reset}>
        Try again
      </Button>
    </div>
  )
}

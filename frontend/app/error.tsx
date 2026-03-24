'use client'

import { AlertTriangle, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
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
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 p-8">
      <div className="relative">
        <div className="absolute -inset-6 rounded-full bg-loss/8 blur-2xl" />
        <div className="relative rounded-full border border-loss/20 bg-loss/10 p-5 shadow-lg">
          <AlertTriangle className="h-10 w-10 text-loss" />
        </div>
      </div>
      <div className="space-y-3 text-center">
        <p className="text-xs font-semibold uppercase tracking-widest text-loss/70">
          Error
        </p>
        <h2 className="font-display italic text-3xl text-text">Something went wrong</h2>
        <p className="max-w-md text-sm leading-relaxed text-text-muted">
          An unexpected error occurred. Try refreshing, or click the button below
          to recover.
        </p>
        {error.digest ? (
          <p className="text-xs text-text-muted/50">Error ID: {error.digest}</p>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" asChild>
          <Link href="/">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Dashboard
          </Link>
        </Button>
        <Button type="button" onClick={reset}>
          Try again
        </Button>
      </div>
    </div>
  )
}

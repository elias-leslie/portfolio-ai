'use client'

import { AlertTriangle, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'

export default function MoneyError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Money page error:', error)
  }, [error])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 p-8">
      <div className="relative">
        <div className="absolute -inset-6 rounded-full bg-loss/8 blur-2xl" />
        <div className="relative rounded-full border border-loss/20 bg-loss/10 p-5 shadow-lg">
          <AlertTriangle className="h-10 w-10 text-loss" />
        </div>
      </div>
      <div className="text-center space-y-3">
        <h2 className="font-display text-2xl text-text">
          Failed to load money workspace
        </h2>
        <p className="max-w-md text-sm text-text-muted leading-relaxed">
          Could not load your household finance data. Try refreshing, or return
          to the dashboard.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" asChild>
          <Link href="/">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Dashboard
          </Link>
        </Button>
        <Button type="button" onClick={reset}>
          Retry
        </Button>
      </div>
    </div>
  )
}

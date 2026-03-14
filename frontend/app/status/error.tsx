'use client'

import { AlertTriangle, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'

export default function StatusError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Status page error:', error)
  }, [error])

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 p-8">
      <div className="rounded-full bg-loss/10 p-4">
        <AlertTriangle className="h-8 w-8 text-loss" />
      </div>
      <div className="text-center space-y-2">
        <h2 className="text-xl font-semibold text-text">
          Failed to load system status
        </h2>
        <p className="max-w-md text-sm text-text-muted leading-relaxed">
          Could not load the system health dashboard. The health check service
          may be temporarily unavailable.
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

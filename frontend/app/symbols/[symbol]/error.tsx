'use client'

import { AlertTriangle } from 'lucide-react'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'

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
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8 p-8">
      <div className="relative">
        <div className="absolute -inset-6 rounded-full bg-loss/8 blur-2xl" />
        <div className="relative rounded-full border border-loss/20 bg-loss/10 p-5 shadow-lg">
          <AlertTriangle className="h-10 w-10 text-loss" />
        </div>
      </div>
      <div className="text-center space-y-3">
        <h2 className="font-display italic text-2xl text-text">
          Failed to load symbol data
        </h2>
        <p className="max-w-md text-sm text-text-muted leading-relaxed">
          Could not load the requested symbol. The data source may be
          temporarily unavailable.
        </p>
      </div>
      <Button type="button" onClick={reset}>
        Retry
      </Button>
    </div>
  )
}

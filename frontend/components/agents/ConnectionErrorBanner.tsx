'use client'

import { Button } from '@/components/ui/button'

interface ConnectionErrorBannerProps {
  error: string
  onRetry: () => void
}

export function ConnectionErrorBanner({
  error,
  onRetry,
}: ConnectionErrorBannerProps) {
  return (
    <div className="p-3 bg-loss/30 border-b border-loss text-loss text-sm">
      {error}
      <Button
        variant="ghost"
        size="sm"
        onClick={onRetry}
        className="ml-2 h-6 text-xs"
      >
        Retry
      </Button>
    </div>
  )
}

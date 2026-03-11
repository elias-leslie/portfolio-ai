'use client'

import { AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface MarketPanelMessageProps {
  message: string
  className?: string
}

export function MarketPanelMessage({
  message,
  className,
}: MarketPanelMessageProps) {
  return (
    <div
      role="status"
      className={cn(
        'flex h-full min-h-32 items-center justify-center gap-2 rounded-xl border border-border/40 bg-surface-muted/20 px-4 text-center text-sm text-text-muted',
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span>{message}</span>
    </div>
  )
}

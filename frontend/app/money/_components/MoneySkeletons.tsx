'use client'

import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export function LoadingState() {
  return (
    <div
      className="flex min-h-72 items-center justify-center rounded-3xl border border-border/40 bg-surface-muted/20"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3 text-sm font-medium text-text-muted">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        Loading money workspace...
      </div>
    </div>
  )
}

const TAB_LABELS = [
  'Dashboard',
  'Budget',
  'Levers',
  'Retirement',
  'Allocation',
  'Accounts',
  'Ledger',
  'Intake',
  'Review',
]

export function MoneyWorkspaceSkeleton() {
  return (
    <div className="space-y-6" role="status" aria-live="polite">
      <span className="sr-only">Loading money workspace</span>
      <div className="rounded-2xl border border-border/40 bg-bg p-3 shadow-sm">
        <div className="flex flex-wrap gap-2">
          {TAB_LABELS.map((label, idx) => (
            <div
              key={label}
              className={cn(
                'h-10 rounded-xl border border-border/30 bg-surface/50 px-4',
                idx === 0 ? 'w-28 animate-pulse bg-primary/10' : 'w-24',
                idx > 0 && 'skeleton',
              )}
            />
          ))}
        </div>
      </div>
      <div className="space-y-4">
        <div className="h-44 rounded-3xl skeleton" />
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="h-56 rounded-3xl skeleton" />
          <div className="h-56 rounded-3xl skeleton" />
        </div>
      </div>
    </div>
  )
}

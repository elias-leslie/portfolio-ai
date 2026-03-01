'use client'

import type { SourceProvider } from '@/lib/api/sources'

interface SourcesSummaryCardsProps {
  providers: SourceProvider[]
}

export function SourcesSummaryCards({ providers }: SourcesSummaryCardsProps) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="text-2xl font-bold text-foreground">
          {providers.length}
        </div>
        <div className="text-sm text-muted-foreground">Total Providers</div>
      </div>
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="text-2xl font-bold text-status-success">
          {providers.filter((p) => p.tier === 'FREE').length}
        </div>
        <div className="text-sm text-muted-foreground">FREE Tier</div>
      </div>
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="text-2xl font-bold text-status-info">
          {new Set(providers.flatMap((p) => p.gapCoverage)).size}
        </div>
        <div className="text-sm text-muted-foreground">GAPs Covered</div>
      </div>
      <div className="rounded-lg border border-border bg-surface p-4">
        <div className="text-2xl font-bold text-foreground">
          {providers.filter((p) => !p.apiKeyRequired).length}
        </div>
        <div className="text-sm text-muted-foreground">No Key Required</div>
      </div>
    </div>
  )
}

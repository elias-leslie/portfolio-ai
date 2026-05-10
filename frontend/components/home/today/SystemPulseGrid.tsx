'use client'

import type { ComponentProps } from 'react'
import {
  describeIntradayMood,
  describePortfolioHealth,
} from '@/components/portfolio/investing-language'
import { Badge } from '@/components/ui/badge'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import type { MarketIntelligenceResponse } from '@/lib/api/market'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'

type BadgeVariant = ComponentProps<typeof Badge>['variant']

function StatusChip({
  label,
  value,
  detail,
  variant = 'outline',
}: {
  label: string
  value: string
  detail?: string | null
  variant?: BadgeVariant
}) {
  return (
    <div className="rounded-2xl border border-border/30 bg-background/20 px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {label}
        </p>
        <Badge
          variant={variant}
          className="h-5 px-2 text-[10px] uppercase tracking-[0.16em]"
        >
          {value}
        </Badge>
      </div>
      {detail ? (
        <p className="mt-1.5 text-[11px] leading-5 text-text-muted">{detail}</p>
      ) : null}
    </div>
  )
}

export interface SystemPulseGridProps {
  household: HouseholdFinanceDashboard | undefined
  householdLoading: boolean
  analytics: PortfolioAnalytics | undefined
  analyticsLoading: boolean
  market: MarketIntelligenceResponse | undefined
  marketLoading: boolean
}

export function SystemPulseGrid({
  household,
  householdLoading,
  analytics,
  analyticsLoading,
  market,
  marketLoading,
}: SystemPulseGridProps) {
  const portfolioHealth = describePortfolioHealth(analytics)
  const marketMood = describeIntradayMood(market)

  return (
    <section className="@container rounded-2xl border border-border/35 bg-surface/35 p-3.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        System Pulse
      </p>
      <div className="mt-3 grid gap-2 @[28rem]:grid-cols-2">
        <StatusChip
          label="Portfolio"
          value={analyticsLoading ? 'Loading' : portfolioHealth.label}
          detail={
            analyticsLoading
              ? 'Checking concentration and spread'
              : portfolioHealth.detail
          }
        />
        <StatusChip
          label="Mood"
          value={marketLoading ? 'Loading' : marketMood.label}
          detail={marketLoading ? 'Reading market state' : marketMood.detail}
        />
        <StatusChip
          label="Visibility"
          value={
            householdLoading || !household
              ? 'Loading'
              : `${household.overview.visibilityScore}/100`
          }
          detail={
            household?.overview.visibilityLabel ?? 'Household evidence quality'
          }
        />
        <StatusChip
          label="Accounts"
          value={
            householdLoading || !household
              ? 'Loading'
              : household.overview.needsRefreshCount > 0
                ? `${household.overview.needsRefreshCount} stale`
                : `${household.overview.trackedAccountCount} live`
          }
          detail={
            household?.overview.needsRefreshCount
              ? `${household.overview.needsRefreshCount} account${household.overview.needsRefreshCount === 1 ? '' : 's'} need fresher evidence.`
              : 'Tracked account set is current.'
          }
          variant={
            household?.overview.needsRefreshCount ? 'secondary' : 'success'
          }
        />
      </div>
    </section>
  )
}

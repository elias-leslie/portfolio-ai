'use client'

import type { ComponentProps } from 'react'
import {
  describeMarketMood,
  describePortfolioHealth,
} from '@/components/portfolio/investing-language'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import type { Badge } from '@/components/ui/badge'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { usePortfolio, usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'

function normalizeQualityStatus(status: string | null | undefined) {
  switch (status) {
    case 'trusted':
      return 'current'
    case 'partial':
      return 'estimated'
    case 'blocked':
      return 'unavailable'
    case 'fresh':
      return 'current'
    case 'aging':
      return 'stale'
    default:
      return status ?? 'unavailable'
  }
}

function qualityBadgeVariant(status: string) {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'success' as const
    case 'estimated':
      return 'warning' as const
    case 'stale':
      return 'secondary' as const
    default:
      return 'outline' as const
  }
}

function qualityLabel(status: string) {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'Current'
    case 'estimated':
      return 'Estimate'
    case 'stale':
      return 'Stale'
    default:
      return 'Unavailable'
  }
}

function OverviewCard({
  label,
  value,
  detail,
  badgeLabel,
  badgeDetail,
  badgeVariant = 'outline',
}: {
  label: string
  value: string
  detail: string
  badgeLabel?: string | null
  badgeDetail?: string | null
  badgeVariant?: ComponentProps<typeof Badge>['variant']
}) {
  return (
    <div className="rounded-2xl border border-border/40 bg-surface/60 px-4 py-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-text-muted">
          {label}
        </p>
        {badgeLabel ? (
          <InfoBadge
            label={badgeLabel}
            detail={badgeDetail ?? undefined}
            variant={badgeVariant}
          />
        ) : null}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-text">
        {value}
      </p>
      <p className="mt-1 text-sm text-text-muted">{detail}</p>
    </div>
  )
}

export function TodayOverviewPanel() {
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio()
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics()
  const { data: market, isLoading: marketLoading } = useMarketIntelligence()

  const marketMood = describeMarketMood(market?.fearGreed)
  const portfolioHealth = describePortfolioHealth(analytics)
  const portfolioValue =
    portfolio?.householdInvestedTotalValue ??
    portfolio?.effectiveTotalValue ??
    portfolio?.totalValue ??
    null
  const portfolioQuoteDetail =
    portfolio?.quotesUpdatedAt != null
      ? `Oldest live quote ${new Date(portfolio.quotesUpdatedAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}.`
      : null

  const cards = [
    {
      label: 'Net Worth',
      value:
        householdLoading || !household
          ? 'Loading…'
          : formatCurrencyWhole(household.overview.netWorth),
      detail: 'Household total',
      badgeLabel: household
        ? qualityLabel(household.overview.netWorthStatus)
        : null,
      badgeDetail: household?.overview.netWorthDetail ?? null,
      badgeVariant: qualityBadgeVariant(
        household?.overview.netWorthStatus ?? 'unavailable',
      ),
    },
    {
      label: 'Monthly Spend',
      value:
        householdLoading || !household
          ? 'Loading…'
          : formatCurrencyWhole(
              household.reports.executive.averageMonthlySpend,
            ),
      detail: 'Recent monthly average',
      badgeLabel: household
        ? qualityLabel(household.overview.monthlySpendStatus)
        : null,
      badgeDetail: household?.overview.monthlySpendDetail ?? null,
      badgeVariant: qualityBadgeVariant(
        household?.overview.monthlySpendStatus ?? 'unavailable',
      ),
    },
    {
      label: 'Visibility',
      value:
        householdLoading || !household
          ? 'Loading…'
          : `${household.overview.visibilityScore}/100`,
      detail: household?.overview.visibilityLabel ?? 'Household visibility',
    },
    {
      label: 'Accounts',
      value:
        householdLoading || !household
          ? 'Loading…'
          : String(household.overview.trackedAccountCount),
      detail: 'Tracked household accounts',
      badgeLabel:
        household && household.overview.needsRefreshCount > 0
          ? `${household.overview.needsRefreshCount} stale`
          : null,
      badgeDetail:
        household && household.overview.needsRefreshCount > 0
          ? `${household.overview.needsRefreshCount} account${household.overview.needsRefreshCount === 1 ? '' : 's'} need fresher evidence.`
          : null,
      badgeVariant:
        household && household.overview.needsRefreshCount > 0
          ? ('secondary' as const)
          : ('outline' as const),
    },
    {
      label: 'Portfolio Value',
      value: portfolioLoading
        ? 'Loading…'
        : formatCurrencyWhole(portfolioValue),
      detail: 'Invested household assets',
      badgeLabel: portfolio?.quoteFreshnessLabel ?? null,
      badgeDetail: portfolioQuoteDetail,
      badgeVariant: qualityBadgeVariant(
        portfolio?.quoteFreshnessStatus ?? 'unavailable',
      ),
    },
    {
      label: 'Total Gain',
      value: portfolioLoading
        ? 'Loading…'
        : formatCurrencyWhole(portfolio?.totalGain),
      detail: 'Live positioned assets',
      badgeLabel: portfolio?.quoteFreshnessLabel ?? null,
      badgeDetail: portfolioQuoteDetail,
      badgeVariant: qualityBadgeVariant(
        portfolio?.quoteFreshnessStatus ?? 'unavailable',
      ),
    },
    {
      label: 'Portfolio Health',
      value: analyticsLoading ? 'Loading…' : portfolioHealth.label,
      detail: analyticsLoading
        ? 'Checking concentration'
        : portfolioHealth.detail,
    },
    {
      label: 'Market Mood',
      value: marketLoading ? 'Loading…' : marketMood.label,
      detail: marketLoading ? 'Checking market state' : marketMood.detail,
    },
  ]

  return (
    <SectionCard
      variant="surface"
      title="Overview"
      description="Global snapshot. Drill down in Money and Investing."
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <OverviewCard key={card.label} {...card} />
        ))}
      </div>
    </SectionCard>
  )
}

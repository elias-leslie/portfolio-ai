'use client'

import type { ComponentProps, ReactNode } from 'react'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { RelativeTime } from '@/components/shared/RelativeTime'
import type { Badge } from '@/components/ui/badge'
import type {
  HouseholdFinanceDashboard,
  HouseholdNetWorthTrend,
} from '@/lib/api/household'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import {
  netWorthBadgeLabel,
  netWorthBadgeVariant,
  qualityBadgeVariant,
  qualityLabel,
  spendPaceBadgeVariant,
} from '@/lib/dataQuality'
import { formatCurrencyWhole } from '@/lib/formatters'
import { NetWorthTrendLine, type TrendPoint } from './NetWorthTrendLine'
import { TileLabel } from './TileLabel'

type BadgeVariant = ComponentProps<typeof Badge>['variant']

interface CompactTileProps {
  label: string
  value: string
  detail: string
  labelDetail?: ReactNode
  badge?: string | null
  badgeDetail?: ReactNode
  badgeVariant?: BadgeVariant
  trend?: TrendPoint[]
  trendLoading?: boolean
}

function CompactOverviewTile({
  label,
  value,
  detail,
  labelDetail,
  badge,
  badgeDetail,
  badgeVariant = 'outline',
  trend,
  trendLoading = false,
}: CompactTileProps) {
  return (
    <article className="rounded-2xl border border-border/35 bg-surface/45 px-3.5 py-3">
      <div className="flex items-start justify-between gap-2">
        <TileLabel label={label} detail={labelDetail} />
        {badge ? (
          <InfoBadge
            label={badge}
            detail={badgeDetail}
            variant={badgeVariant}
            className="h-5 px-2 text-[10px] uppercase tracking-[0.16em]"
          />
        ) : null}
      </div>
      <p className="mt-1.5 text-[1.22rem] font-semibold tracking-tight text-text">
        {value}
      </p>
      <p className="mt-1 text-[11px] leading-4 text-text-muted">{detail}</p>
      {trend ? (
        <NetWorthTrendLine points={trend} loading={trendLoading} />
      ) : null}
    </article>
  )
}

function renderMoneyValue(value: number | null | undefined, loading: boolean) {
  if (loading) {
    return 'Loading…'
  }
  if (value == null) {
    return 'Unavailable'
  }
  return formatCurrencyWhole(value)
}

export interface PrimaryTilesGridProps {
  household: HouseholdFinanceDashboard | undefined
  householdLoading: boolean
  analytics: PortfolioAnalytics | undefined
  analyticsLoading: boolean
  netWorthTrend: HouseholdNetWorthTrend | undefined
  trendLoading: boolean
}

export function PrimaryTilesGrid({
  household,
  householdLoading,
  analytics,
  analyticsLoading,
  netWorthTrend,
  trendLoading,
}: PrimaryTilesGridProps) {
  const netWorthTrendPoints: TrendPoint[] =
    netWorthTrend?.points.map((point) => ({
      date: point.date,
      value: point.netWorth,
    })) ?? []
  const netWorthTrendLatest =
    netWorthTrendPoints.length > 0
      ? netWorthTrendPoints[netWorthTrendPoints.length - 1]?.value
      : null
  const netWorth = netWorthTrendLatest ?? household?.overview.netWorth ?? null
  const netWorthStatus =
    netWorthTrend?.status ?? household?.overview.netWorthStatus ?? null

  // Only the household.overview value is invested-only. analytics.effectiveTotalValue
  // and analytics.portfolioValue.totalValue both include cash, so falling back to them
  // mislabels Invested + Cash as "Invested" when overview is missing.
  const investedAssets = household?.overview.investedAssets ?? null
  const cashReserve = household?.overview.cashReserve ?? null
  const cashReserveMonths =
    household?.portfolioContext?.cashReservesMonths ?? null

  const monthToDateVariance =
    household?.budgetSnapshot.monthToDatePlan != null
      ? household.budgetSnapshot.monthToDateSpend -
        household.budgetSnapshot.monthToDatePlan
      : null

  // Tile value and badge both derive from backend paceStatus so they can never disagree.
  // The variance amount only annotates the value when the backend says we are off plan.
  const paceStatus = household?.budgetSnapshot.paceStatus ?? null
  let spendPaceValue: string
  if (householdLoading || !household) {
    spendPaceValue = 'Loading…'
  } else if (paceStatus === 'on_track') {
    spendPaceValue = 'On plan'
  } else if (
    (paceStatus === 'running_hot' || paceStatus === 'under_plan') &&
    monthToDateVariance != null
  ) {
    const sign = monthToDateVariance > 0 ? '+' : '−'
    spendPaceValue = `${sign}${formatCurrencyWhole(Math.abs(monthToDateVariance))}`
  } else {
    spendPaceValue = (paceStatus ?? 'unavailable').replaceAll('_', ' ')
  }

  const investedFreshnessStatus =
    analytics?.quoteFreshnessStatus ?? 'unavailable'
  const investedFreshnessLabel =
    analyticsLoading && !analytics
      ? 'Loading'
      : qualityLabel(investedFreshnessStatus)
  const investedFreshnessDetail: ReactNode = analytics?.quotesUpdatedAt ? (
    <>
      Market prices refreshed <RelativeTime value={analytics.quotesUpdatedAt} />
      .
    </>
  ) : analyticsLoading ? (
    'Checking the latest market prices now.'
  ) : (
    'Uses the latest available market prices for invested balances.'
  )

  const tiles: CompactTileProps[] = [
    {
      label: 'Net Worth',
      value: renderMoneyValue(netWorth, householdLoading && !household),
      detail: 'Known holdings and balances minus debt',
      labelDetail:
        'Uses actual tracked portfolio shares with latest cached prices where symbols are linked. Cash, debt, and non-symbol accounts use latest available balance evidence.',
      badge: netWorthStatus ? netWorthBadgeLabel(netWorthStatus) : null,
      badgeDetail: (
        <div className="space-y-1">
          <p>{netWorthTrend?.detail ?? household?.overview.netWorthDetail}</p>
          {netWorthTrend?.methodology ? (
            <p>{netWorthTrend.methodology}</p>
          ) : null}
        </div>
      ),
      badgeVariant: netWorthBadgeVariant(netWorthStatus),
      trend: netWorthTrendPoints,
      trendLoading,
    },
    {
      label: 'Invested',
      value: renderMoneyValue(investedAssets, householdLoading && !household),
      detail: 'Money currently in investments',
      labelDetail:
        'Retirement and brokerage assets. Cash kept on the side stays out.',
      badge: investedFreshnessLabel,
      badgeDetail: investedFreshnessDetail,
      badgeVariant: qualityBadgeVariant(investedFreshnessStatus),
    },
    {
      label: 'Cash Reserve',
      value: renderMoneyValue(cashReserve, householdLoading && !household),
      detail: 'Cash available before selling assets',
      labelDetail:
        'Cash you can use now without selling long-term investments.',
      badge:
        cashReserveMonths != null ? `${cashReserveMonths.toFixed(1)} mo` : null,
      badgeDetail:
        cashReserveMonths != null
          ? `Cash reserve covers about ${cashReserveMonths.toFixed(1)} months of essential spending.`
          : 'Months of cash runway will appear once essential spending coverage is available.',
      badgeVariant: 'outline',
    },
    {
      label: 'Spend Pace',
      value: spendPaceValue,
      detail: household ? 'This month vs plan' : 'Budget pacing unavailable',
      labelDetail:
        'Shows whether this month is running below, near, or above your spending plan.',
      badge: household
        ? household.budgetSnapshot.paceStatus.replaceAll('_', ' ')
        : null,
      badgeDetail: household?.budgetSnapshot.paceDetail,
      badgeVariant: spendPaceBadgeVariant(household?.budgetSnapshot.paceStatus),
    },
  ]

  return (
    <div className="@container">
      <div className="grid gap-3 @[36rem]:grid-cols-2">
        {tiles.map((tile) => (
          <CompactOverviewTile key={tile.label} {...tile} />
        ))}
      </div>
    </div>
  )
}

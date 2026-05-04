'use client'

import type { ComponentProps, ReactNode } from 'react'
import {
  describeIntradayMood,
  describePortfolioHealth,
  intradayMoodScore,
} from '@/components/portfolio/investing-language'
import { InfoBadge } from '@/components/shared/InfoBadge'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { HomeTodayBriefMetric } from '@/lib/api/home'
import type {
  EnrichedIndicator,
  MarketIntelligenceResponse,
} from '@/lib/api/market'
import { formatCurrencyWhole } from '@/lib/formatters'
import { useHomeTodayBrief } from '@/lib/hooks/useHomeTodayBrief'
import { useHouseholdDashboard } from '@/lib/hooks/useHousehold'
import { useMarketIntelligence } from '@/lib/hooks/useMarketIntelligence'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { cn, formatRelativeTime } from '@/lib/utils'

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

function qualityBadgeVariant(
  status: string,
): ComponentProps<typeof Badge>['variant'] {
  switch (normalizeQualityStatus(status)) {
    case 'current':
      return 'success'
    case 'estimated':
      return 'warning'
    case 'stale':
      return 'secondary'
    default:
      return 'outline'
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

function paceVariant(
  status: string | null | undefined,
): ComponentProps<typeof Badge>['variant'] {
  switch ((status ?? '').toLowerCase()) {
    case 'on_track':
    case 'within_plan':
    case 'under_plan':
      return 'success'
    case 'above_plan':
    case 'over_plan':
    case 'watch':
      return 'warning'
    default:
      return 'outline'
  }
}

function metricToneClasses(tone: string) {
  switch (tone) {
    case 'positive':
      return 'border-gain/25 bg-gain/8'
    case 'negative':
      return 'border-loss/25 bg-loss/8'
    case 'warning':
      return 'border-warning/25 bg-warning/8'
    default:
      return 'border-border/30 bg-background/25'
  }
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

function formatMarketAsOf(value?: string | null) {
  if (!value) {
    return 'As of time unavailable'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return 'As of time unavailable'
  }
  return `As of ${parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })}`
}

function formatEtMarketAsOf(value?: string | null) {
  if (!value) {
    return null
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  return `As of ${parsed.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/New_York',
  })} ET`
}

function formatMetricNumber(value: number | null | undefined, digits = 2) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'Unavailable'
  }
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function indicatorAsOf(
  indicator: EnrichedIndicator | undefined,
  fallback?: string | null,
) {
  return indicator?.lastUpdated ?? fallback ?? null
}

function buildLiveMarketMetrics(
  market: MarketIntelligenceResponse | undefined,
): HomeTodayBriefMetric[] | null {
  if (!market?.indicators || !market.sectorRotation) {
    return null
  }
  const sp500 = market.indicators.sp500
  const vix = market.indicators.vix
  const tnx = market.indicators.tnx
  if (!sp500 || !vix || !tnx) {
    return null
  }

  const leading = market.sectorRotation.leading.slice(0, 3)
  const leadership = leading
    .map((sector) => sector.name)
    .filter(Boolean)
    .join(', ')
  const marketAsOf = market.lastUpdated
  const sp500AsOf = indicatorAsOf(sp500, marketAsOf)
  const vixAsOf = indicatorAsOf(vix, marketAsOf)
  const tnxAsOf = indicatorAsOf(tnx, marketAsOf)
  const leadershipAsOf = leading[0]?.lastUpdated ?? marketAsOf
  const moodScore = intradayMoodScore(market)
  const mood = describeIntradayMood(market)

  return [
    {
      key: 'sp500',
      label: 'S&P 500',
      value: formatMetricNumber(sp500.value),
      changePct: sp500.changePct,
      detail: 'Broad market benchmark',
      horizon: 'Current quote · 1D vs prior close',
      asOf: sp500AsOf,
      asOfLabel: formatEtMarketAsOf(sp500AsOf),
      tone: (sp500.changePct ?? 0) > 0 ? 'positive' : 'negative',
    },
    {
      key: 'vix',
      label: 'VIX',
      value: formatMetricNumber(vix.value),
      changePct: vix.changePct,
      detail: 'Risk pricing',
      horizon: 'Current quote · 1D vs prior close',
      asOf: vixAsOf,
      asOfLabel: formatEtMarketAsOf(vixAsOf),
      tone: vix.value < 20 ? 'positive' : 'warning',
    },
    {
      key: 'tnx',
      label: '10Y Yield',
      value: `${formatMetricNumber(tnx.value, 3)}%`,
      changePct: tnx.changePct,
      detail: 'Rate pressure',
      horizon: 'Current quote · 1D vs prior close',
      asOf: tnxAsOf,
      asOfLabel: formatEtMarketAsOf(tnxAsOf),
      tone: tnx.value >= 4.5 ? 'warning' : 'neutral',
    },
    {
      key: 'intraday_mood',
      label: 'Intraday Mood',
      value: moodScore?.toString() ?? '—',
      changePct: null,
      detail: mood.label,
      horizon: 'Live proxy · Quote inputs',
      asOf: marketAsOf,
      asOfLabel: formatEtMarketAsOf(marketAsOf),
      tone:
        mood.tone === 'gain'
          ? 'positive'
          : mood.tone === 'warning' || mood.tone === 'loss'
            ? 'warning'
            : 'neutral',
    },
    {
      key: 'leadership',
      label: 'Leadership',
      value: leadership || 'Mixed',
      changePct: leading[0]?.changePct ?? null,
      detail: 'Sectors leading today',
      horizon: 'Current quotes · 1D sectors',
      asOf: leadershipAsOf,
      asOfLabel: formatEtMarketAsOf(leadershipAsOf),
      tone: leading.length > 0 ? 'positive' : 'neutral',
    },
  ]
}

function TileLabel({ label, detail }: { label: string; detail?: ReactNode }) {
  if (!detail) {
    return (
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
        {label}
      </p>
    )
  }

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex cursor-help appearance-none border-0 bg-transparent p-0 text-left outline-none"
            aria-label={`${label}: more detail`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
              {label}
            </p>
          </button>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm text-xs leading-relaxed">
          {detail}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function CompactOverviewTile({
  label,
  value,
  detail,
  labelDetail,
  badge,
  badgeDetail,
  badgeVariant = 'outline',
}: {
  label: string
  value: string
  detail: string
  labelDetail?: ReactNode
  badge?: string | null
  badgeDetail?: ReactNode
  badgeVariant?: ComponentProps<typeof Badge>['variant']
}) {
  return (
    <article className="rounded-[22px] border border-border/35 bg-surface/45 px-3.5 py-3">
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
    </article>
  )
}

type CompactOverviewTileProps = ComponentProps<typeof CompactOverviewTile>

function StatusChip({
  label,
  value,
  detail,
  variant = 'outline',
}: {
  label: string
  value: string
  detail?: string | null
  variant?: ComponentProps<typeof Badge>['variant']
}) {
  return (
    <div className="rounded-2xl border border-border/30 bg-background/20 px-3 py-2.5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {label}
        </p>
        <Badge
          variant={variant}
          className="h-5 px-2 text-[10px] uppercase tracking-[0.14em]"
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

function MarketStripItem({ metric }: { metric: HomeTodayBriefMetric }) {
  return (
    <div
      className={cn(
        'rounded-2xl border px-3 py-3',
        metricToneClasses(metric.tone),
        metric.key === 'leadership' && 'sm:col-span-2',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
          {metric.label}
        </p>
        {metric.changePct != null ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-text-muted">
            {metric.changePct > 0 ? '+' : ''}
            {metric.changePct.toFixed(2)}%
          </span>
        ) : null}
      </div>
      <p
        className={cn(
          'mt-1.5 font-semibold tracking-tight text-text',
          metric.key === 'leadership'
            ? 'text-[13px] leading-5'
            : 'text-[1.05rem] leading-none',
        )}
      >
        {metric.value}
      </p>
      <p className="mt-1 text-[10px] uppercase tracking-[0.18em] text-text-muted">
        {metric.detail}
      </p>
      <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-muted/80">
        {metric.horizon ?? 'Horizon unavailable'} ·{' '}
        {metric.asOfLabel ?? formatMarketAsOf(metric.asOf)}
      </p>
    </div>
  )
}

export function TodayOverviewPanel() {
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics()
  const { data: market, isLoading: marketLoading } = useMarketIntelligence()
  const { data: todayBrief, isLoading: briefLoading } = useHomeTodayBrief()

  const marketMood = describeIntradayMood(market)
  const portfolioHealth = describePortfolioHealth(analytics)
  const netWorth = household?.overview.netWorth ?? null
  const investedAssets =
    household?.overview.investedAssets ??
    analytics?.householdInvestedTotalValue ??
    analytics?.effectiveTotalValue ??
    analytics?.portfolioValue.totalValue ??
    null
  const cashReserve =
    household?.overview.cashReserve ?? analytics?.householdCashReserve ?? null
  const cashReserveMonths =
    household?.portfolioContext?.cashReservesMonths ?? null
  const monthToDateVariance =
    household?.budgetSnapshot.monthToDatePlan != null
      ? household.budgetSnapshot.monthToDateSpend -
        household.budgetSnapshot.monthToDatePlan
      : null
  const spendPaceValue =
    householdLoading || !household
      ? 'Loading…'
      : monthToDateVariance == null
        ? household.budgetSnapshot.paceStatus.replaceAll('_', ' ')
        : Math.abs(monthToDateVariance) < 25
          ? 'On plan'
          : formatCurrencyWhole(monthToDateVariance)
  const investedFreshnessStatus =
    analytics?.quoteFreshnessStatus ?? 'unavailable'
  const investedFreshnessLabel =
    analyticsLoading && !analytics
      ? 'Loading'
      : qualityLabel(investedFreshnessStatus)
  const investedFreshnessDetail = analytics?.quotesUpdatedAt
    ? `Market prices refreshed ${formatRelativeTime(analytics.quotesUpdatedAt)}.`
    : analyticsLoading
      ? 'Checking the latest market prices now.'
      : 'Uses the latest available market prices for invested balances.'

  const primaryTiles: CompactOverviewTileProps[] = [
    {
      label: 'Net Worth',
      value: renderMoneyValue(netWorth, householdLoading && !household),
      detail: 'Everything you own minus debt',
      labelDetail:
        'Uses tracked household accounts and subtracts known credit and loan balances.',
      badge: household ? qualityLabel(household.overview.netWorthStatus) : null,
      badgeDetail: household?.overview.netWorthDetail,
      badgeVariant: qualityBadgeVariant(
        household?.overview.netWorthStatus ?? 'unavailable',
      ),
    },
    {
      label: 'Invested',
      value: renderMoneyValue(
        investedAssets,
        householdLoading && analyticsLoading && investedAssets == null,
      ),
      detail: 'Money currently in investments',
      labelDetail:
        'Retirement and brokerage assets. Cash kept on the side stays out.',
      badge: investedFreshnessLabel,
      badgeDetail: investedFreshnessDetail,
      badgeVariant: qualityBadgeVariant(investedFreshnessStatus),
    },
    {
      label: 'Cash Reserve',
      value: renderMoneyValue(
        cashReserve,
        householdLoading && analyticsLoading && cashReserve == null,
      ),
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
      badgeVariant: paceVariant(household?.budgetSnapshot.paceStatus),
    },
  ]

  const liveMarketMetrics = buildLiveMarketMetrics(market)
  const marketMetrics = liveMarketMetrics ?? todayBrief?.marketMetrics ?? []
  const marketStripTimestamp = liveMarketMetrics
    ? market?.lastUpdated
    : todayBrief?.generatedAt
  const scanNotes = todayBrief?.brief.bullets.slice(0, 2) ?? [
    portfolioHealth.detail,
    marketMood.detail,
  ]

  return (
    <SectionCard
      variant="surface"
      title="Overview"
      description="Household state, market tape, and data quality in one compact rail."
      padding="sm"
      headerClassName="px-5 py-4"
      className="h-full"
    >
      <div className="flex h-full flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          {primaryTiles.map((tile) => (
            <CompactOverviewTile key={tile.label} {...tile} />
          ))}
        </div>

        <section className="rounded-[24px] border border-border/35 bg-surface/35 p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
                Market Strip
              </p>
              <h3 className="mt-1 font-display text-base italic tracking-tight text-text">
                Tape that matters to this portfolio
              </h3>
            </div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
              {marketStripTimestamp
                ? `${liveMarketMetrics ? 'Market data' : 'Generated'} ${formatRelativeTime(marketStripTimestamp)}`
                : briefLoading
                  ? 'Loading tape'
                  : 'Update time unavailable'}
            </p>
          </div>

          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {briefLoading && marketMetrics.length === 0
              ? [...Array(5)].map((_, index) => (
                  <div
                    key={`overview-market-strip-skeleton-${index}`}
                    className={cn(
                      'h-[4.75rem] rounded-2xl skeleton',
                      index === 4 && 'sm:col-span-2',
                    )}
                  />
                ))
              : marketMetrics.map((metric) => (
                  <MarketStripItem key={metric.key} metric={metric} />
                ))}
          </div>
        </section>

        <div className="grid gap-3 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section className="rounded-[24px] border border-border/35 bg-surface/35 p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
              System Pulse
            </p>
            <div className="mt-3 grid gap-2">
              <StatusChip
                label="Portfolio"
                value={analyticsLoading ? 'Loading' : portfolioHealth.label}
                detail={
                  analyticsLoading
                    ? 'Checking concentration and spread'
                    : portfolioHealth.detail
                }
                variant="outline"
              />
              <StatusChip
                label="Mood"
                value={marketLoading ? 'Loading' : marketMood.label}
                detail={
                  marketLoading ? 'Reading market state' : marketMood.detail
                }
                variant="outline"
              />
              <StatusChip
                label="Visibility"
                value={
                  householdLoading || !household
                    ? 'Loading'
                    : `${household.overview.visibilityScore}/100`
                }
                detail={
                  household?.overview.visibilityLabel ??
                  'Household evidence quality'
                }
                variant="outline"
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
                  household?.overview.needsRefreshCount
                    ? 'secondary'
                    : 'success'
                }
              />
            </div>
          </section>

          <section className="rounded-[24px] border border-border/35 bg-surface/35 p-3.5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
                Scan Notes
              </p>
              {todayBrief?.marketStatus ? (
                <Badge
                  variant="outline"
                  className="h-5 px-2 text-[10px] uppercase tracking-[0.16em]"
                >
                  {todayBrief.marketStatus.replaceAll('_', ' ')}
                </Badge>
              ) : null}
            </div>

            <div className="mt-3 space-y-2">
              {scanNotes.map((note, index) => (
                <div
                  key={`${index}-${note}`}
                  className="rounded-2xl border border-border/30 bg-background/20 px-3 py-2.5"
                >
                  <div className="flex gap-2.5">
                    <span className="pt-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
                      {(index + 1).toString().padStart(2, '0')}
                    </span>
                    <p className="text-[12px] leading-5 text-text">{note}</p>
                  </div>
                </div>
              ))}
            </div>

            {todayBrief?.stalenessNotes.length ? (
              <div className="mt-3 rounded-2xl border border-warning/25 bg-warning/8 px-3 py-2.5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-warning">
                  Confidence drag
                </p>
                <p className="mt-1 text-[12px] leading-5 text-text-muted">
                  {todayBrief.stalenessNotes[0]}
                </p>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </SectionCard>
  )
}

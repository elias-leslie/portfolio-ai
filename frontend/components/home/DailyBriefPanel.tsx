'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import {
  DEFAULT_MARKET_TIMEFRAME,
  timeframeToDays,
} from '@/components/market/TimeframeSelector'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import type { MacroSnapshot } from '@/lib/api/macro'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import type { WatchlistItem } from '@/lib/api/watchlist'
import type { CommitteeRunListItem } from '@/lib/committee/api'
import { fetchCommitteeRuns } from '@/lib/committee/api'
import {
  netWorthBadgeLabel,
  normalizeQualityStatus,
  qualityLabel,
} from '@/lib/dataQuality'
import { formatCurrencyWhole, formatEnumLabel } from '@/lib/formatters'
import { useHomeActionQueue } from '@/lib/hooks/useHomeActionQueue'
import {
  useHouseholdDashboard,
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import {
  useMarketIntelligence,
  useMarketStatus,
  useSectorHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { useBlendedSignals, useMacroCurrent } from '@/lib/hooks/useSignals'
import { useWatchlist } from '@/lib/hooks/useWatchlist'
import { cn } from '@/lib/utils'
import {
  buildLiveMarketMetrics,
  type MarketStripMetric,
} from './today/MarketStripGrid'

interface ZoneStyle {
  label: string
  className: string
  description: string
}

const ZONE_STYLES: Record<string, ZoneStyle> = {
  FULL_DEPLOY: {
    label: 'Full Deploy',
    className: 'border-gain/40 bg-gain/10 text-gain',
    description: 'Conditions support adding risk from the strongest setups.',
  },
  REDUCED: {
    label: 'Reduced',
    className: 'border-warning/45 bg-warning/10 text-warning',
    description:
      'Scan only top-quartile setups. Trim weak positions before adding risk.',
  },
  DEFENSIVE: {
    label: 'Defensive',
    className: 'border-loss/45 bg-loss/10 text-loss',
    description: 'Do not add new risk until the macro gate improves.',
  },
}

const COMPONENT_LABELS: Array<{
  key: keyof MacroSnapshot['components']
  label: string
}> = [
  { key: 'vix', label: 'VIX' },
  { key: 'term', label: 'Term' },
  { key: 'breadth', label: 'Breadth' },
  { key: 'credit', label: 'Credit' },
  { key: 'putcall', label: 'Put/Call' },
  { key: 'crowding', label: 'Crowding' },
]

function isToday(iso?: string | null): boolean {
  if (!iso) return false
  const date = new Date(iso)
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

function formatScore(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(0)
    : '-'
}

function formatTimestamp(value?: string | null): string {
  if (!value) return 'Update time unavailable'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return 'Update time unavailable'
  const formatted = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
  return `Updated ${formatted} ET`
}

function formatMoney(value: number | null | undefined, loading: boolean) {
  if (loading) return 'Loading...'
  return formatCurrencyWhole(value, { nullDisplay: '-' })
}

function scoreTone(value: number | null | undefined): string {
  if (value == null) return 'bg-border-subtle'
  if (value >= 70) return 'bg-gain/80'
  if (value >= 40) return 'bg-warning/80'
  return 'bg-loss/80'
}

function marketTone(metric: MarketStripMetric): string {
  switch (metric.tone) {
    case 'positive':
      return 'border-gain/30 bg-gain/8'
    case 'negative':
      return 'border-loss/30 bg-loss/8'
    case 'warning':
      return 'border-warning/30 bg-warning/8'
    default:
      return 'border-border/35 bg-bg/25'
  }
}

function sectorSummaryText(
  sectors: { name: string; currentPct: number }[],
  fallback: string,
) {
  if (sectors.length === 0) return fallback
  return sectors
    .map(
      (sector) =>
        `${sector.name} ${sector.currentPct >= 0 ? '+' : ''}${sector.currentPct.toFixed(1)}%`,
    )
    .join(' / ')
}

function useCommitteeRunsToday() {
  const [runs, setRuns] = useState<CommitteeRunListItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchCommitteeRuns(20)
      .then((res) => {
        if (cancelled) return
        const todays = res.runs.filter((run) =>
          isToday(run.completed_at ?? run.started_at),
        )
        setRuns(todays.slice(0, 3))
        setError(null)
      })
      .catch((err: Error) => {
        if (cancelled) return
        setRuns([])
        setError(err.message)
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { runs, error }
}

function resolveZoneStyle(zone: string | null | undefined): ZoneStyle {
  const key = zone?.toUpperCase()
  return (
    (key && ZONE_STYLES[key]) || {
      label: key ? formatEnumLabel(key) : '-',
      className: 'border-border-subtle bg-surface/60 text-text-muted',
      description: 'Deployment posture is loading.',
    }
  )
}

function deploymentDate(snapshotDate: string | null | undefined): string {
  return snapshotDate ?? '-'
}

function capitalMetrics({
  household,
  analytics,
  netWorthTrend,
  householdLoading,
}: {
  household?: HouseholdFinanceDashboard
  analytics?: PortfolioAnalytics
  netWorthTrend?: { points: { netWorth: number }[]; status?: string | null }
  householdLoading: boolean
}) {
  const trendLatest = netWorthTrend?.points.at(-1)?.netWorth ?? null
  const netWorth = trendLatest ?? household?.overview.netWorth ?? null
  const accountControl = household?.accountControl
  const accountBlocked = Boolean(
    accountControl && accountControl.blockingIssueCount > 0,
  )
  const netWorthStatus = accountBlocked
    ? 'blocked'
    : (netWorthTrend?.status ?? household?.overview.netWorthStatus ?? null)
  const investedFreshness = analytics?.quoteFreshnessStatus ?? 'unavailable'
  const cashReserveMonths =
    household?.portfolioContext?.cashReservesMonths ?? null
  const paceStatus = household?.budgetSnapshot.paceStatus ?? null
  const monthToDateVariance =
    household?.budgetSnapshot.monthToDatePlan != null
      ? household.budgetSnapshot.monthToDateSpend -
        household.budgetSnapshot.monthToDatePlan
      : null
  let spendPace = 'Loading...'
  if (household) {
    if (paceStatus === 'on_track') {
      spendPace = 'On plan'
    } else if (
      (paceStatus === 'running_hot' || paceStatus === 'under_plan') &&
      monthToDateVariance != null
    ) {
      const sign = monthToDateVariance > 0 ? '+' : '-'
      spendPace = `${sign}${formatCurrencyWhole(Math.abs(monthToDateVariance))}`
    } else {
      spendPace = formatEnumLabel(paceStatus, 'Unavailable')
    }
  }

  return [
    {
      label: 'Net Worth',
      value: formatMoney(netWorth, householdLoading && !household),
      detail: netWorthBadgeLabel(netWorthStatus),
      tone:
        normalizeQualityStatus(netWorthStatus) === 'current'
          ? 'text-gain'
          : normalizeQualityStatus(netWorthStatus) === 'stale'
            ? 'text-warning'
            : 'text-text-muted',
    },
    {
      label: 'Invested',
      value: formatMoney(
        household?.overview.investedAssets ?? null,
        householdLoading && !household,
      ),
      detail: qualityLabel(investedFreshness),
      tone:
        normalizeQualityStatus(investedFreshness) === 'current'
          ? 'text-gain'
          : 'text-text-muted',
    },
    {
      label: 'Cash',
      value: formatMoney(
        household?.overview.cashReserve ?? null,
        householdLoading && !household,
      ),
      detail:
        cashReserveMonths != null ? `${cashReserveMonths.toFixed(1)} mo` : '-',
      tone: 'text-text-muted',
    },
    {
      label: 'Spend Pace',
      value: spendPace,
      detail: formatEnumLabel(paceStatus, '-'),
      tone:
        paceStatus === 'running_hot' || paceStatus === 'above_plan'
          ? 'text-warning'
          : 'text-text-muted',
    },
  ]
}

function ComponentScoreTile({
  label,
  value,
}: {
  label: string
  value: number | null | undefined
}) {
  const pct =
    typeof value === 'number' && Number.isFinite(value)
      ? Math.max(0, Math.min(100, value))
      : 0

  return (
    <div className="rounded-xl border border-border-subtle bg-bg/30 px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-text-muted">
        {label}
      </p>
      <p className="mt-1.5 font-mono text-lg tabular-nums text-text">
        {formatScore(value)}
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border-subtle/70">
        <div
          className={cn('h-full rounded-full', scoreTone(value))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

function ActionQueue({ watchlistItems }: { watchlistItems: WatchlistItem[] }) {
  const {
    data: scannerData,
    isLoading: scannerLoading,
    error: scannerError,
  } = useBlendedSignals({ limit: 5 })
  const { runs, error: committeeError } = useCommitteeRunsToday()
  const scannerRows = scannerData?.rows ?? []
  const alerts = watchlistItems
    .filter((item) => (item.signalStrength ?? 0) >= 70)
    .sort((a, b) => (b.signalStrength ?? 0) - (a.signalStrength ?? 0))
    .slice(0, 3)

  return (
    <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
        Action Queue
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-[1.1fr_0.95fr_0.8fr]">
        <div className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-text">Scanner</h3>
            <span className="whitespace-nowrap font-mono text-xs font-semibold text-warning">
              top 5
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {scannerError ? (
              <p className="text-xs text-loss">
                {scannerError instanceof Error
                  ? scannerError.message
                  : 'Scanner unavailable'}
              </p>
            ) : scannerLoading ? (
              <p className="text-xs text-text-muted">Loading scanner...</p>
            ) : scannerRows.length === 0 ? (
              <p className="text-xs text-text-muted">No candidates today.</p>
            ) : (
              scannerRows.slice(0, 5).map((row) => (
                <div
                  key={row.symbol}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <Link
                    href={`/symbols/${row.symbol}`}
                    className="font-mono font-semibold text-primary hover:underline"
                  >
                    {row.symbol}
                  </Link>
                  <span className="font-mono text-xs tabular-nums text-text">
                    #{row.blendedRank} {row.blendedScore.toFixed(1)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-text">Committee</h3>
            <span className="font-mono text-xs font-semibold text-warning">
              {runs === null ? '...' : `${runs.length} today`}
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {committeeError ? (
              <p className="text-xs text-loss">{committeeError}</p>
            ) : runs === null ? (
              <p className="text-xs text-text-muted">Loading verdicts...</p>
            ) : runs.length === 0 ? (
              <p className="text-xs text-text-muted">No verdicts today.</p>
            ) : (
              runs.map((run) => (
                <div
                  key={run.id}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <Link
                    href={`/portfolio/committee/${run.id}`}
                    className="font-mono font-semibold text-primary hover:underline"
                  >
                    {run.symbol}
                  </Link>
                  <span className="text-xs text-text">
                    {run.decision_action ?? run.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-text">Watchlist</h3>
            <span className="font-mono text-xs font-semibold text-warning">
              {alerts.length > 0 ? `${alerts.length} hot` : 'quiet'}
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {alerts.length === 0 ? (
              <p className="text-xs leading-5 text-text-muted">
                No high-strength alerts.
              </p>
            ) : (
              alerts.map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <Link
                    href={`/symbols/${item.symbol}`}
                    className="font-mono font-semibold text-primary hover:underline"
                  >
                    {item.symbol}
                  </Link>
                  <span className="font-mono text-xs tabular-nums text-text">
                    {item.signalStrength ?? '-'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function SideContext({
  household,
  analytics,
  marketMetrics,
  householdLoading,
}: {
  household?: HouseholdFinanceDashboard
  analytics?: PortfolioAnalytics
  marketMetrics: MarketStripMetric[]
  householdLoading: boolean
}) {
  const { data: netWorthTrend } = useHouseholdNetWorthTrend({ days: 180 })
  const {
    data: sectorHistory,
    isLoading: sectorsLoading,
    error: sectorError,
  } = useSectorHistory(timeframeToDays(DEFAULT_MARKET_TIMEFRAME))
  const sortedSectors = useMemo(() => {
    if (!sectorHistory?.sectors) return []
    return [...sectorHistory.sectors].sort(
      (a, b) => (b.currentPct ?? 0) - (a.currentPct ?? 0),
    )
  }, [sectorHistory?.sectors])
  const leading = sectorsLoading
    ? 'Updating leaders...'
    : sectorError
      ? 'Unable to rank sectors'
      : sectorSummaryText(sortedSectors.slice(0, 3), 'Still populating')
  const lagging = sectorsLoading
    ? 'Updating laggards...'
    : sectorError
      ? 'Unable to rank sectors'
      : sectorSummaryText(sortedSectors.slice(-3).reverse(), 'Still populating')
  const capital = capitalMetrics({
    household,
    analytics,
    netWorthTrend,
    householdLoading,
  })

  return (
    <div className="space-y-3 rounded-2xl border border-border-subtle bg-bg/20 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
        Capital Context
      </p>
      <div className="grid grid-cols-2 gap-2">
        {capital.map((metric) => (
          <div
            key={metric.label}
            className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-2.5"
          >
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
              {metric.label}
            </p>
            <p className="mt-1 font-semibold leading-none tracking-tight text-text">
              {metric.value}
            </p>
            <p className={cn('mt-1 text-[10px]', metric.tone)}>
              {metric.detail}
            </p>
          </div>
        ))}
      </div>

      <div className="border-t border-border-subtle pt-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
          Market Context
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {marketMetrics.map((metric) => (
            <div
              key={metric.key}
              className={cn(
                'rounded-xl border px-3 py-2.5',
                marketTone(metric),
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
                  {metric.label}
                </p>
                {metric.changePct != null ? (
                  <span className="font-mono text-[10px] text-text-muted">
                    {metric.changePct > 0 ? '+' : ''}
                    {metric.changePct.toFixed(2)}%
                  </span>
                ) : null}
              </div>
              <p className="mt-1 font-semibold leading-none tracking-tight text-text">
                {metric.value}
              </p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-text-muted">
                {metric.detail}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-3 space-y-2 text-xs leading-5 text-text">
          <p>
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
              Leading
            </span>
            <br />
            {leading}
          </p>
          <p>
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-muted">
              Lagging
            </span>
            <br />
            {lagging}
          </p>
        </div>
      </div>
    </div>
  )
}

export function DailyBriefPanel() {
  const {
    data: macro,
    isLoading: macroLoading,
    error: macroError,
  } = useMacroCurrent()
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: analytics } = usePortfolioAnalytics()
  const { data: market, isLoading: marketLoading } = useMarketIntelligence()
  const { data: marketStatus } = useMarketStatus()
  const { data: watchlist } = useWatchlist()
  const { data: actions } = useHomeActionQueue()
  const zoneStyle = resolveZoneStyle(macro?.zone)
  const marketMetrics =
    buildLiveMarketMetrics(market, {
      marketIsOpen: marketStatus?.isOpen ?? false,
    }) ?? []
  const updateTimestamp =
    market?.lastUpdated ?? macro?.computedAt ?? household?.generatedAt ?? null
  const actionCount = actions?.actions.length ?? 0

  return (
    <section className="overflow-hidden rounded-2xl border border-border/40 bg-surface/50 surface-highlight backdrop-blur-sm">
      <div className="flex flex-col gap-2 border-b border-border/40 px-6 py-5 md:flex-row md:items-center md:justify-between">
        <h2 className="font-display italic text-lg tracking-tight text-text">
          Daily Brief
        </h2>
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
          {formatTimestamp(updateTimestamp)}
        </p>
      </div>

      <div className="grid items-start gap-4 p-4 xl:grid-cols-[minmax(18rem,0.72fr)_minmax(34rem,1.18fr)_minmax(22rem,0.78fr)]">
        <div
          className={cn(
            'rounded-2xl border px-5 py-5 xl:min-h-[16.5rem]',
            zoneStyle.className,
          )}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="rounded-full border border-current px-3 py-1 text-[10px] font-bold uppercase tracking-[0.18em]">
              {macroLoading && !macro ? 'Loading' : zoneStyle.label}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-current/70">
              {deploymentDate(macro?.snapshotDate)}
            </span>
          </div>
          <div className="mt-6 flex items-baseline gap-2">
            <span className="font-display italic text-7xl leading-none tracking-tight tabular-nums">
              {formatScore(macro?.deploymentScore)}
            </span>
            <span className="text-sm text-current/70">/ 100</span>
          </div>
          <p className="mt-3 max-w-[31rem] text-sm leading-6 text-current/85">
            {macroError
              ? macroError instanceof Error
                ? macroError.message
                : 'Deployment posture unavailable.'
              : zoneStyle.description}
          </p>
          <div className="mt-5 space-y-1 font-mono text-[11px] uppercase tracking-[0.16em] text-current/75">
            <p>
              Coverage{' '}
              {macro?.coverage != null
                ? `${Math.round(macro.coverage * 100)}%`
                : '-'}
            </p>
            <p>Next refresh after 17:30 ET</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4">
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
              Why
            </p>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {COMPONENT_LABELS.map(({ key, label }) => (
                <ComponentScoreTile
                  key={key}
                  label={label}
                  value={macro?.components?.[key] ?? null}
                />
              ))}
            </div>
          </div>

          <ActionQueue watchlistItems={watchlist?.items ?? []} />
        </div>

        <SideContext
          household={household}
          analytics={analytics}
          marketMetrics={marketMetrics}
          householdLoading={householdLoading}
        />
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 border-t border-border-subtle px-6 py-3 text-xs text-text-muted">
        <span>
          <strong className="text-text">Status:</strong>{' '}
          {marketStatus?.isOpen ? 'market open' : 'market closed'}
        </span>
        <span>
          <strong className="text-text">Quotes:</strong>{' '}
          {qualityLabel(analytics?.quoteFreshnessStatus)}
        </span>
        <span>
          <strong className="text-text">Net worth:</strong>{' '}
          {household?.overview.netWorthStatus
            ? netWorthBadgeLabel(household.overview.netWorthStatus)
            : '-'}
        </span>
        <span>
          <strong className="text-text">Alerts:</strong> {actionCount} open
        </span>
        {marketLoading ? (
          <span>
            <strong className="text-text">Market:</strong> loading
          </span>
        ) : null}
      </div>
    </section>
  )
}

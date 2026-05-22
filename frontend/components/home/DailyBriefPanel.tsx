'use client'

import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import type { MacroSnapshot } from '@/lib/api/macro'
import type { PortfolioAnalytics } from '@/lib/api/portfolio'
import {
  netWorthBadgeLabel,
  normalizeQualityStatus,
  qualityLabel,
} from '@/lib/dataQuality'
import { formatCurrencyWhole, formatEnumLabel } from '@/lib/formatters'
import {
  useHouseholdDashboard,
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import { useMarketStatus } from '@/lib/hooks/useMarketIntelligence'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { useMacroCurrent } from '@/lib/hooks/useSignals'
import { cn } from '@/lib/utils'

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
  rawKey: keyof MacroSnapshot['raw']
  rawLabel: string
}> = [
  { key: 'vix', label: 'VIX', rawKey: 'vixClose', rawLabel: 'VIX' },
  {
    key: 'term',
    label: 'Term',
    rawKey: 'termSpreadBps',
    rawLabel: '10Y-2Y bps',
  },
  {
    key: 'breadth',
    label: 'Breadth',
    rawKey: 'breadthPct',
    rawLabel: '% > 200d',
  },
  { key: 'credit', label: 'Credit', rawKey: 'hySpread', rawLabel: 'HY OAS' },
  {
    key: 'putcall',
    label: 'Put/Call',
    rawKey: 'putCallRatio',
    rawLabel: 'P/C',
  },
  {
    key: 'crowding',
    label: 'Crowding',
    rawKey: 'factorCrowdingCorr',
    rawLabel: 'corr',
  },
]

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

function formatRawComponent(
  key: keyof MacroSnapshot['raw'],
  value: number | null | undefined,
) {
  if (value == null || !Number.isFinite(value)) return '-'
  switch (key) {
    case 'vixClose':
      return value.toFixed(2)
    case 'termSpreadBps':
      return `${value.toFixed(0)} bps`
    case 'breadthPct':
      return `${value.toFixed(1)}%`
    case 'hySpread':
      return `${value.toFixed(2)}%`
    case 'putCallRatio':
      return value.toFixed(2)
    case 'factorCrowdingCorr':
      return value.toFixed(2)
    default:
      return value.toFixed(2)
  }
}

function qualityTone(status?: string) {
  if (status === 'missing') return 'text-loss'
  if (status === 'stale') return 'text-warning'
  return 'text-gain'
}

function MacroContributionBreakdown({ macro }: { macro?: MacroSnapshot }) {
  const weights = macro?.weights ?? {}
  const availableWeight = COMPONENT_LABELS.reduce((sum, component) => {
    const score = macro?.components?.[component.key]
    const weight = weights[component.key] ?? 0
    return score == null ? sum : sum + weight
  }, 0)
  const rows = COMPONENT_LABELS.map((component) => {
    const score = macro?.components?.[component.key] ?? null
    const baseWeight = weights[component.key] ?? 0
    const effectiveWeight =
      score != null && availableWeight > 0 ? baseWeight / availableWeight : 0
    const contribution = score != null ? score * effectiveWeight : null
    const quality = macro?.componentQuality?.[component.key]
    return {
      ...component,
      score,
      rawValue: macro?.raw?.[component.rawKey] ?? null,
      baseWeight,
      effectiveWeight,
      contribution,
      quality,
    }
  })
  const missingRows = rows.filter((row) => row.score == null)

  return (
    <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
            Regime Score Breakdown
          </p>
          <p className="mt-2 text-xs leading-5 text-text-muted">
            Score = Σ(component score × effective weight). Missing components
            are excluded, and the remaining weights are renormalized.
          </p>
        </div>
        <div className="rounded-xl border border-border-subtle bg-bg/30 px-3 py-2 text-right">
          <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
            Coverage
          </p>
          <p className="font-mono text-lg font-semibold text-text">
            {macro?.coverage != null
              ? `${Math.round(macro.coverage * 100)}%`
              : '-'}
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {rows.map((row) => {
          const contributionPct =
            row.contribution != null
              ? Math.max(0, Math.min(100, row.contribution))
              : 0
          return (
            <div
              key={row.key}
              className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-text">{row.label}</p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-[0.14em] text-text-muted">
                    {row.rawLabel}:{' '}
                    {formatRawComponent(row.rawKey, row.rawValue)}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-right font-mono text-xs tabular-nums">
                  <span className="text-text">
                    Score {formatScore(row.score)}
                  </span>
                  <span className="text-text-muted">
                    Base {(row.baseWeight * 100).toFixed(0)}%
                  </span>
                  <span className="text-text-muted">
                    Eff {(row.effectiveWeight * 100).toFixed(1)}%
                  </span>
                  <span className="text-text">
                    +
                    {row.contribution != null
                      ? row.contribution.toFixed(1)
                      : '-'}
                  </span>
                </div>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-border-subtle/70">
                <div
                  className={cn('h-full rounded-full', scoreTone(row.score))}
                  style={{ width: `${contributionPct}%` }}
                />
              </div>
              <p className="mt-2 text-[10px] leading-4 text-text-muted">
                <span className={qualityTone(row.quality?.status)}>
                  {(row.quality?.status ?? 'unknown').toUpperCase()}
                </span>
                {row.quality?.asOf ? ` · as of ${row.quality.asOf}` : ''}
                {row.quality?.source ? ` · ${row.quality.source}` : ''}
                {row.quality?.reason ? ` · ${row.quality.reason}` : ''}
              </p>
            </div>
          )
        })}
      </div>

      {missingRows.length > 0 ? (
        <p className="mt-3 rounded-xl border border-loss/25 bg-loss/8 px-3 py-2 text-xs leading-5 text-loss">
          Missing score input: {missingRows.map((row) => row.label).join(', ')}.
          Fix the feed or remove the component from the score; do not treat this
          as a fully covered regime reading.
        </p>
      ) : null}
    </div>
  )
}

function CapitalContext({
  household,
  analytics,
  householdLoading,
}: {
  household?: HouseholdFinanceDashboard
  analytics?: PortfolioAnalytics
  householdLoading: boolean
}) {
  const { data: netWorthTrend } = useHouseholdNetWorthTrend({ days: 180 })
  const capital = capitalMetrics({
    household,
    analytics,
    netWorthTrend,
    householdLoading,
  })

  return (
    <div className="space-y-3 rounded-2xl border border-border-subtle bg-bg/20 p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
        Portfolio Snapshot
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
  const { data: marketStatus } = useMarketStatus()
  const zoneStyle = resolveZoneStyle(macro?.zone)
  const updateTimestamp = macro?.computedAt ?? household?.generatedAt ?? null

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

      <div className="grid items-start gap-4 p-4 xl:grid-cols-[minmax(18rem,0.72fr)_minmax(36rem,1.25fr)_minmax(20rem,0.7fr)]">
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

        <MacroContributionBreakdown macro={macro} />

        <CapitalContext
          household={household}
          analytics={analytics}
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
      </div>
    </section>
  )
}

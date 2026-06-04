'use client'

import { Info, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { HouseholdFinanceDashboard } from '@/lib/api/household'
import type {
  MacroConditionEvidence,
  MacroConditionShift,
  MacroConditionsResponse,
  MacroConditionTrend,
  MacroSnapshot,
} from '@/lib/api/macro'
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
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { useMacroConditions, useMacroCurrent } from '@/lib/hooks/useSignals'
import { useTodayRefresh } from '@/lib/hooks/useTodayRefresh'
import { cn } from '@/lib/utils'

interface ZoneStyle {
  label: string
  className: string
  description: string
}

const CONDITION_STYLES: Record<string, ZoneStyle> = {
  Calm: {
    label: 'Calm',
    className: 'border-gain/40 bg-gain/10 text-gain',
    description: 'Conditions are supportive.',
  },
  Caution: {
    label: 'Caution',
    className: 'border-warning/45 bg-warning/10 text-warning',
    description: 'Conditions call for selectivity, not panic.',
  },
  Elevated: {
    label: 'Elevated',
    className: 'border-loss/45 bg-loss/10 text-loss',
    description: 'Stress is high enough to prioritize protection.',
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

function resolveConditionStyle(state: string | null | undefined): ZoneStyle {
  return state && CONDITION_STYLES[state]
    ? CONDITION_STYLES[state]
    : {
        label: state ?? '-',
        className: 'border-border-subtle bg-surface/60 text-text-muted',
        description: 'Market conditions are loading.',
      }
}

function deploymentDate(snapshotDate: string | null | undefined): string {
  return snapshotDate ?? '-'
}

function macroZoneState(zone: string | null | undefined): string | undefined {
  const normalized = zone?.toUpperCase()
  if (normalized === 'FULL_DEPLOY') return 'Calm'
  if (normalized === 'DEFENSIVE') return 'Elevated'
  if (normalized === 'REDUCED') return 'Caution'
  return undefined
}

function conditionBadge(
  state: string | undefined,
  alertActive: boolean,
  loading: boolean,
): string {
  if (loading && !state) return 'Loading'
  if (!state) return '-'
  if (state === 'Caution' && !alertActive) {
    return 'Caution, not emergency'
  }
  if (state === 'Elevated') return 'Elevated stress'
  return state
}

function formatPercent(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value)
    ? `${Math.round(value * 100)}%`
    : '-'
}

function evidenceToneClass(tone: string): string {
  if (tone === 'gain') return 'border-gain/30 bg-gain/8 text-gain'
  if (tone === 'warning') return 'border-warning/35 bg-warning/8 text-warning'
  if (tone === 'loss') return 'border-loss/35 bg-loss/8 text-loss'
  return 'border-border-subtle bg-bg/25 text-text-muted'
}

function trendTextClass(tone: string): string {
  if (tone === 'gain') return 'text-gain'
  if (tone === 'warning') return 'text-warning'
  if (tone === 'loss') return 'text-loss'
  return 'text-text-muted'
}

function shiftToneClass(tone: string): string {
  if (tone === 'gain') return 'border-gain/30 bg-gain/8 text-gain'
  if (tone === 'warning') return 'border-warning/35 bg-warning/8 text-warning'
  if (tone === 'loss') return 'border-loss/35 bg-loss/8 text-loss'
  return 'border-border-subtle bg-bg/30 text-text-muted'
}

function Sparkline({
  points,
  tone,
  className,
}: {
  points?: number[]
  tone: string
  className?: string
}) {
  const values = points?.filter((value) => Number.isFinite(value)) ?? []
  if (values.length < 2) {
    return (
      <span className={cn('block h-4 w-10 rounded bg-current/10', className)} />
    )
  }

  const width = 64
  const height = 24
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const path = values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width
      const y = height - ((value - min) / range) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <svg
      className={cn(
        'h-4 w-10 overflow-visible',
        trendTextClass(tone),
        className,
      )}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <polyline
        points={path}
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.5"
      />
    </svg>
  )
}

function TrendChip({
  trend,
  compact = false,
}: {
  trend?: MacroConditionTrend | null
  compact?: boolean
}) {
  if (!trend || trend.direction === 'unavailable') return null
  return (
    <span
      className={cn(
        'flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em]',
        trendTextClass(trend.tone),
      )}
      title={trend.summary}
    >
      <Sparkline
        points={trend.sparkline}
        tone={trend.tone}
        className={compact ? 'h-3.5 w-8' : 'h-5 w-14'}
      />
      <span>{trend.changeLabel}</span>
    </span>
  )
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

function MarketConditionHero({
  conditions,
  macro,
  loading,
  error,
}: {
  conditions?: MacroConditionsResponse
  macro?: MacroSnapshot
  loading: boolean
  error: unknown
}) {
  const state = conditions?.state ?? macroZoneState(macro?.zone)
  const alertActive = conditions?.alert.active ?? state === 'Elevated'
  const stateStyle = resolveConditionStyle(state)
  const stressScore =
    conditions?.stressScore ??
    (macro?.deploymentScore != null
      ? Math.round(100 - macro.deploymentScore)
      : null)
  const deploymentScore = conditions?.deploymentScore ?? macro?.deploymentScore
  const coverage = conditions?.coverage ?? macro?.coverage
  const summary = error
    ? error instanceof Error
      ? error.message
      : 'Market conditions unavailable.'
    : (conditions?.summary ?? stateStyle.description)
  const actionText =
    conditions?.actionText ??
    'Use the macro gate as context before adding new market risk.'
  const stressTrend = conditions?.trend?.stress

  return (
    <div
      className={cn(
        'rounded-2xl border px-5 py-4 xl:min-h-[14.5rem]',
        stateStyle.className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="rounded-full border border-current px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] sm:px-3">
          {conditionBadge(state, alertActive, loading)}
        </span>
        <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.16em] text-current/70">
          {deploymentDate(conditions?.snapshotDate ?? macro?.snapshotDate)}
        </span>
      </div>

      <div className="mt-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-current/70">
          Market Stress
        </p>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-display italic text-6xl leading-none tracking-tight tabular-nums">
            {formatScore(stressScore)}
          </span>
          <span className="text-sm text-current/70">/ 100</span>
        </div>
        {stressTrend && stressTrend.direction !== 'unavailable' ? (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <TrendChip trend={stressTrend} />
            <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-current/70">
              {stressTrend.reversalLabel ?? stressTrend.summary}
            </span>
          </div>
        ) : null}
      </div>

      <p className="mt-3 text-sm font-semibold leading-5 text-current">
        {summary}
      </p>
      <p className="mt-2 text-xs leading-5 text-current/80">{actionText}</p>

      <div className="mt-4 grid grid-cols-2 gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-current/75">
        <div className="rounded-xl border border-current/20 bg-bg/15 px-3 py-2">
          <p>Deployment</p>
          <p className="mt-1 text-sm font-semibold tracking-normal text-current">
            {formatScore(deploymentScore)}
          </p>
        </div>
        <div className="rounded-xl border border-current/20 bg-bg/15 px-3 py-2">
          <p>Coverage</p>
          <p className="mt-1 text-sm font-semibold tracking-normal text-current">
            {formatPercent(coverage)}
          </p>
        </div>
      </div>
    </div>
  )
}

function BriefingList({
  title,
  items,
  fallback,
}: {
  title: string
  items?: string[]
  fallback: string
}) {
  const displayItems = items?.length ? items.slice(0, 4) : [fallback]

  return (
    <div className="rounded-xl border border-border-subtle bg-bg/25 px-3 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        {title}
      </p>
      <ul className="mt-2 space-y-1.5 text-xs leading-5 text-text-muted">
        {displayItems.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-[0.45rem] h-1 w-1 shrink-0 rounded-full bg-primary/70" />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function MarketShifts({ shifts }: { shifts?: MacroConditionShift[] }) {
  const displayShifts = shifts?.length
    ? shifts.slice(0, 3)
    : [
        {
          key: 'loading',
          label: 'Trend history loading',
          detail: 'Waiting for market history.',
          tone: 'neutral',
          reversal: false,
        },
      ]

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">
        Market shifts
      </span>
      {displayShifts.map((shift) => (
        <span
          key={shift.key}
          className={cn(
            'rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]',
            shiftToneClass(shift.tone),
          )}
          title={shift.detail}
        >
          {shift.label}
        </span>
      ))}
    </div>
  )
}

function DecisionBrief({
  conditions,
}: {
  conditions?: MacroConditionsResponse
}) {
  const alertLabel = !conditions
    ? 'Loading'
    : conditions.alert.active
      ? 'Alert active'
      : 'No stress alert'

  return (
    <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4 xl:min-h-[14.5rem]">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-text-muted">
            Today Briefing
          </p>
          <p className="mt-1 text-sm font-semibold text-text">
            What matters, what to do, and what would change the read.
          </p>
        </div>
        <span
          className={cn(
            'w-fit rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em]',
            conditions?.alert.active
              ? 'border-loss/35 bg-loss/8 text-loss'
              : 'border-border-subtle bg-bg/30 text-text-muted',
          )}
        >
          {alertLabel}
        </span>
      </div>

      <MarketShifts shifts={conditions?.marketShifts} />

      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <BriefingList
          title="What matters"
          items={conditions?.whatMatters}
          fallback="Market evidence is loading."
        />
        <BriefingList
          title="What to do"
          items={conditions?.whatToDo}
          fallback="Keep allocation decisions tied to the written plan."
        />
        <BriefingList
          title="What changes this"
          items={conditions?.watchItems}
          fallback="Watch volatility, credit, breadth, and the macro score."
        />
      </div>
    </div>
  )
}

function MarketEvidenceStrip({
  evidence,
}: {
  evidence?: MacroConditionEvidence[]
}) {
  if (!evidence?.length) {
    return (
      <div className="border-t border-border-subtle px-4 py-3 text-xs text-text-muted">
        Market evidence is loading.
      </div>
    )
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="border-t border-border-subtle px-4 py-3">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {evidence.map((item) => (
            <div
              key={item.key}
              className={cn(
                'rounded-xl border px-3 py-2.5',
                evidenceToneClass(item.tone),
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-current/75">
                  {item.label}
                </p>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="rounded-full text-current/60 transition hover:text-current focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                      aria-label={`Explain ${item.label}`}
                    >
                      <Info className="h-3.5 w-3.5" aria-hidden="true" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="top" className="max-w-xs">
                    <p className="text-xs leading-5">{item.tooltip}</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <p className="mt-1 font-mono text-lg font-semibold leading-none tabular-nums text-current">
                {item.value}
              </p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <p className="min-w-0 truncate text-[10px] text-current/70">
                  {item.detail}
                </p>
                <TrendChip trend={item.trend} compact />
              </div>
            </div>
          ))}
        </div>
      </div>
    </TooltipProvider>
  )
}

function CapitalContext({
  household,
  analytics,
  householdLoading,
  className,
}: {
  household?: HouseholdFinanceDashboard
  analytics?: PortfolioAnalytics
  householdLoading: boolean
  className?: string
}) {
  const { data: netWorthTrend } = useHouseholdNetWorthTrend({ days: 180 })
  const capital = capitalMetrics({
    household,
    analytics,
    netWorthTrend,
    householdLoading,
  })

  return (
    <div
      className={cn(
        'space-y-3 rounded-2xl border border-border-subtle bg-bg/20 p-4',
        className,
      )}
    >
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
  const refreshToday = useTodayRefresh()
  const {
    data: macro,
    isLoading: macroLoading,
    error: macroError,
  } = useMacroCurrent()
  const {
    data: conditions,
    isLoading: conditionsLoading,
    error: conditionsError,
  } = useMacroConditions()
  const { data: household, isLoading: householdLoading } =
    useHouseholdDashboard()
  const { data: analytics } = usePortfolioAnalytics()
  const updateTimestamp =
    conditions?.computedAt ??
    macro?.computedAt ??
    household?.generatedAt ??
    null

  return (
    <section className="overflow-hidden rounded-2xl border border-border/40 bg-surface/50 surface-highlight backdrop-blur-sm">
      <div className="flex flex-col gap-2 border-b border-border/40 px-6 py-4 md:flex-row md:items-center md:justify-between">
        <h2 className="font-display italic text-lg tracking-tight text-text">
          Daily Brief
        </h2>
        <div className="flex flex-wrap items-center gap-2 md:justify-end">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
            {formatTimestamp(updateTimestamp)}
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refreshToday.mutate()}
            disabled={refreshToday.isPending}
            aria-busy={refreshToday.isPending}
            title="Force-refresh Today with current quotes and recomputed macro conditions"
          >
            {refreshToday.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCw className="h-3.5 w-3.5" />
            )}
            Refresh
          </Button>
        </div>
      </div>

      <div className="grid items-start gap-4 p-4 lg:grid-cols-[minmax(17rem,0.68fr)_minmax(34rem,1.4fr)] xl:grid-cols-[minmax(17rem,0.68fr)_minmax(34rem,1.4fr)_minmax(18rem,0.7fr)]">
        <MarketConditionHero
          conditions={conditions}
          macro={macro}
          loading={
            (macroLoading && !macro) || (conditionsLoading && !conditions)
          }
          error={conditionsError ?? macroError}
        />

        <DecisionBrief conditions={conditions} />

        <CapitalContext
          household={household}
          analytics={analytics}
          householdLoading={householdLoading}
          className="lg:col-span-2 xl:col-span-1"
        />
      </div>

      <MarketEvidenceStrip evidence={conditions?.evidence} />

      <details className="mx-4 mb-4">
        <summary className="cursor-pointer rounded-xl border border-border-subtle bg-bg/20 px-4 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-text-muted transition hover:text-text">
          Score details
        </summary>
        <div className="mt-3">
          <MacroContributionBreakdown macro={macro} />
        </div>
      </details>
    </section>
  )
}

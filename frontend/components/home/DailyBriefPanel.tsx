'use client'

import { Info, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type {
  MacroConditionEvidence,
  MacroConditionShift,
  MacroConditionsResponse,
  MacroConditionTrend,
  MacroSnapshot,
  OvernightLean,
} from '@/lib/api/macro'
import {
  useHouseholdDashboard,
  useHouseholdNetWorthTrend,
} from '@/lib/hooks/useHousehold'
import { useMacroConditions, useMacroCurrent } from '@/lib/hooks/useMacro'
import { usePortfolioAnalytics } from '@/lib/hooks/usePortfolio'
import { useTodayRefresh } from '@/lib/hooks/useTodayRefresh'
import { cn } from '@/lib/utils'
import { OverallCautionTrendLine } from './OverallCautionTrendLine'
import { LeadingLaggingStrip } from './today/LeadingLaggingStrip'
import { PrimaryTilesGrid } from './today/PrimaryTilesGrid'

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

function formatHeldAsOf(value?: string | null): string | null {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
  }).format(parsed)
}

const CATALYST_LABELS: Record<string, string> = {
  fomc_decision: 'Fed rate decision',
  cpi_release: 'Inflation report (CPI)',
  ppi_release: 'Producer prices (PPI)',
  pce_release: 'Inflation report (PCE)',
  gdp_release: 'GDP growth',
  nfp_release: 'Jobs report',
}

function catalystLabel(eventType: string, title: string): string {
  return CATALYST_LABELS[eventType] ?? title
}

function formatCatalystDate(value: string | null | undefined): string | null {
  if (!value) return null
  // event_date is a date-only string ("2026-06-10"); build a local date so it
  // does not shift a day under timezone conversion.
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!match) return null
  const parsed = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  )
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(parsed)
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

function readToState(read: string | null | undefined): string | undefined {
  if (read === 'normal') return 'Calm'
  if (read === 'selective') return 'Caution'
  if (read === 'defensive') return 'Elevated'
  return undefined
}

function fallbackRead(state: string | null | undefined): string {
  if (state === 'Calm') return 'normal'
  if (state === 'Elevated') return 'defensive'
  if (state === 'Caution') return 'selective'
  return 'unavailable'
}

function readLabel(read: string | null | undefined): string {
  if (read === 'normal') return 'Normal'
  if (read === 'selective') return 'Selective'
  if (read === 'defensive') return 'Defensive'
  return 'Unavailable'
}

function driverLabel(driver: string | null | undefined): string {
  if (driver === 'macro') return 'Macro'
  if (driver === 'tape') return 'Tape'
  if (driver === 'both') return 'Both'
  if (driver === 'none') return 'None'
  if (driver === 'data_limited') return 'Data Limited'
  return 'Unavailable'
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
  read: string | undefined,
  alertActive: boolean,
  loading: boolean,
): string {
  if (loading && (!read || read === 'unavailable')) return 'Loading'
  if (!read || read === 'unavailable') return '-'
  if (read === 'selective' && !alertActive) return 'Selective'
  if (read === 'defensive') return 'Defensive'
  if (read === 'normal') return 'Normal'
  return readLabel(read)
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

function drivingToneClass(tone: string): string {
  switch (tone) {
    case 'risk_off':
      return 'border-loss/60 bg-loss/8 text-loss'
    case 'caution':
      return 'border-warning/60 bg-warning/8 text-warning'
    case 'constructive':
      return 'border-gain/60 bg-gain/8 text-gain'
    default:
      return 'border-border-subtle bg-bg/20 text-text-muted'
  }
}

function overnightDirectionLabel(direction: string): string {
  switch (direction) {
    case 'risk_off':
      return 'Leaning risk-off'
    case 'risk_on':
      return 'Leaning risk-on'
    case 'neutral':
      return 'Mixed / quiet'
    default:
      return 'Read unavailable'
  }
}

function overnightToneClass(direction: string): string {
  switch (direction) {
    case 'risk_off':
      return 'border-warning/50 bg-warning/8'
    case 'risk_on':
      return 'border-gain/50 bg-gain/8'
    default:
      return 'border-current/20 bg-bg/15'
  }
}

function overnightDriveLabel(lean: OvernightLean): string {
  if (lean.droveCaution) return '↑ lifting caution'
  return 'context only'
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
  const overallRead = conditions?.overallRead ?? fallbackRead(state)
  const stateStyle = resolveConditionStyle(
    overallRead === 'unavailable'
      ? undefined
      : (readToState(overallRead) ?? state),
  )
  const overallCautionScore =
    conditions?.overallCautionScore ??
    conditions?.stressScore ??
    (macro?.deploymentScore != null
      ? Math.round(100 - macro.deploymentScore)
      : null)
  const deploymentScore = conditions?.deploymentScore ?? macro?.deploymentScore
  const tapePressureScore = conditions?.tapePressureScore
  const tapeStatus = conditions?.tapeStatus
  const tapeHeld = conditions?.tapeState === 'held'
  const tapeHeldAsOf = formatHeldAsOf(conditions?.tapeAsOf)
  // Held tape still contributes its (non-null) score, so only paint "macro-only"
  // when the tape is truly unavailable — never for a held reading.
  const tapeUnavailable = conditions?.tapeAvailable === false && !tapeHeld
  const nextCatalyst = conditions?.nextCatalyst ?? null
  const nextCatalystDate = formatCatalystDate(nextCatalyst?.eventDate)
  // Forward off-hours read. Only surfaced when it applies (markets shut); during
  // RTH the live tape leads and the backend sends applies=false.
  const overnightLean = conditions?.overnightLean?.applies
    ? conditions.overnightLean
    : null
  const primaryDriver = conditions?.primaryDriver ?? 'data_limited'
  const coverage = conditions?.coverage ?? macro?.coverage
  const summary = error
    ? error instanceof Error
      ? error.message
      : 'Market conditions unavailable.'
    : (conditions?.summary ?? stateStyle.description)
  const actionText =
    conditions?.actionText ??
    'Use the macro gate as context before adding new market risk.'
  const degraded = macro?.degraded ?? false
  const staleLabels = (macro?.staleComponents ?? [])
    .map((key) => COMPONENT_LABELS.find((c) => c.key === key)?.label ?? key)
    .join(', ')

  return (
    <div className={cn('rounded-2xl border px-5 py-4', stateStyle.className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-current px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.18em] sm:px-3">
            {conditionBadge(overallRead, alertActive, loading)}
          </span>
          {degraded ? (
            <span
              className="rounded-full border border-warning/60 bg-warning/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-warning"
              title={
                staleLabels
                  ? `Stale input(s) excluded and the score held to the last trusted reading: ${staleLabels}`
                  : 'Running on stale inputs; score held to the last trusted reading.'
              }
            >
              Degraded
            </span>
          ) : null}
        </div>
        <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.16em] text-current/70">
          {deploymentDate(conditions?.snapshotDate ?? macro?.snapshotDate)}
        </span>
      </div>

      <div className="mt-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-current/70">
          Overall Read
        </p>
        <div className="mt-1 flex flex-wrap items-end gap-x-3 gap-y-1">
          <span className="font-display italic text-5xl leading-none tracking-tight sm:text-6xl">
            {readLabel(overallRead)}
          </span>
          <span className="pb-1 font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-current/70">
            Overall Caution {formatScore(overallCautionScore)}/100
          </span>
        </div>
      </div>

      <p className="mt-3 text-sm font-semibold leading-5 text-current">
        {summary}
      </p>
      <p className="mt-2 text-xs leading-5 text-current/80">{actionText}</p>

      {conditions?.driving?.headline ? (
        <div
          className={cn(
            'mt-3 rounded-xl border-l-2 px-3 py-2',
            drivingToneClass(conditions.driving.tone),
          )}
        >
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
            What&apos;s driving
          </p>
          <p className="mt-0.5 text-xs font-medium leading-5">
            {conditions.driving.headline}
          </p>
        </div>
      ) : null}

      {degraded ? (
        <p className="mt-3 rounded-xl border border-warning/30 bg-warning/8 px-3 py-2 text-[11px] leading-4 text-warning">
          Degraded reading: stale input
          {staleLabels ? ` (${staleLabels})` : ''} excluded, so coverage is
          reduced and the score is held to the last trusted gate rather than
          reading calmer on carried-forward data.
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-2 gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-current/75">
        <div
          className="rounded-xl border border-current/20 bg-bg/15 px-3 py-2"
          title="How favorable the macro backdrop is for new buys. 80+ means normal adding, the 60s mean selective adding, and below 40 means defensive."
        >
          <p>Buying Conditions</p>
          <p className="mt-1 text-sm font-semibold tracking-normal text-current">
            {formatScore(deploymentScore)}
          </p>
        </div>
        <div
          className="rounded-xl border border-current/20 bg-bg/15 px-3 py-2"
          title={
            tapeStatus ??
            'Current market action from fresh S&P 500 and sector quotes. Unavailable means tape data is stale or too partial.'
          }
        >
          <p>Tape Pressure</p>
          <p className="mt-1 text-sm font-semibold tracking-normal text-current">
            {formatScore(tapePressureScore)}
          </p>
          {tapeHeld ? (
            <p className="mt-0.5 text-[9px] font-medium normal-case tracking-normal text-current/70">
              {tapeHeldAsOf
                ? `Held · as of ${tapeHeldAsOf}`
                : 'Held · last live tape'}
            </p>
          ) : tapeUnavailable ? (
            <p className="mt-0.5 text-[9px] font-medium normal-case tracking-normal text-current/70">
              {conditions?.marketSession === 'closed'
                ? 'Market closed · macro-only'
                : 'Tape unavailable · macro-only'}
            </p>
          ) : null}
        </div>
        <div
          className="rounded-xl border border-current/20 bg-bg/15 px-3 py-2"
          title={
            conditions?.driverDetail ?? 'Main reason behind the Today read.'
          }
        >
          <p>Driver</p>
          <p className="mt-1 text-sm font-semibold tracking-normal text-current">
            {driverLabel(primaryDriver)}
          </p>
        </div>
        <div
          className="rounded-xl border border-current/20 bg-bg/15 px-3 py-2"
          title="Share of macro drivers currently present in the score. This is data coverage, not a real-time guarantee."
        >
          <p>Coverage</p>
          <p className="mt-1 text-sm font-semibold tracking-normal text-current">
            {formatPercent(coverage)}
          </p>
        </div>
        {nextCatalyst ? (
          <div
            className="col-span-2 rounded-xl border border-current/20 bg-bg/15 px-3 py-2"
            title={`${nextCatalyst.title} — the next high-impact macro event the market is positioning for.`}
          >
            <p>Next Catalyst</p>
            <p className="mt-1 text-sm font-semibold normal-case tracking-normal text-current">
              {catalystLabel(nextCatalyst.eventType, nextCatalyst.title)}
              {nextCatalystDate ? ` · ${nextCatalystDate}` : ''}
            </p>
          </div>
        ) : null}
        {overnightLean ? (
          <div
            className={cn(
              'col-span-2 rounded-xl border px-3 py-2',
              overnightToneClass(overnightLean.direction),
            )}
            title={`${overnightLean.sessionLabel}. Forward read from overnight futures, gold, oil and crypto — it nudges caution while the market is closed, but never overrides the live tape.`}
          >
            <div className="flex items-center justify-between gap-2">
              <p>Overnight</p>
              <p className="text-[9px] font-medium normal-case tracking-normal opacity-70">
                {overnightDriveLabel(overnightLean)}
              </p>
            </div>
            <p className="mt-1 text-sm font-semibold normal-case tracking-normal text-current">
              {overnightDirectionLabel(overnightLean.direction)}
              {overnightLean.liveCount > 0 &&
              overnightLean.direction !== 'unavailable' &&
              overnightLean.direction !== 'neutral'
                ? ` · ${overnightLean.confidence} of ${overnightLean.liveCount} agree`
                : ''}
            </p>
            <p className="mt-1 text-[11px] font-medium normal-case leading-4 tracking-normal text-current/80">
              {overnightLean.headline}
            </p>
          </div>
        ) : null}
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
    <div className="rounded-2xl border border-border-subtle bg-bg/20 p-4">
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
  const { data: analytics, isLoading: analyticsLoading } =
    usePortfolioAnalytics()
  const { data: netWorthTrend, isLoading: trendLoading } =
    useHouseholdNetWorthTrend({ days: 180 })
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

      <div className="grid items-start gap-4 p-4 lg:grid-cols-[minmax(16rem,0.82fr)_minmax(30rem,1.7fr)]">
        <MarketConditionHero
          conditions={conditions}
          macro={macro}
          loading={
            (macroLoading && !macro) || (conditionsLoading && !conditions)
          }
          error={conditionsError ?? macroError}
        />

        <div className="flex flex-col gap-4">
          <DecisionBrief conditions={conditions} />
          <PrimaryTilesGrid
            household={household}
            householdLoading={householdLoading}
            analytics={analytics}
            analyticsLoading={analyticsLoading}
            netWorthTrend={netWorthTrend}
            trendLoading={trendLoading}
          />
          <LeadingLaggingStrip />
          <OverallCautionTrendLine />
        </div>
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

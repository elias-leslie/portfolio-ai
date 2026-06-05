'use client'

import { AlertCircle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import type { PriceTrend, VwapSignal, WatchlistItem } from '@/lib/api/watchlist'
import { cn } from '@/lib/utils'
import { getScoreBadgeVariant, getScoreBarColor } from './ExpandedRowUtils'
import { formatDate, formatPillarStatus } from './watchlistTableUtils'

export interface TodayGate {
  label: string
  tone: 'clear' | 'caution' | 'defensive' | 'degraded'
  detail: string
}

function roundScore(value?: number | null) {
  return typeof value === 'number' && Number.isFinite(value)
    ? value.toFixed(0)
    : '—'
}

function formatPct(value?: number | null) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return `${value >= 0 ? '+' : ''}${value.toFixed(Math.abs(value) >= 10 ? 0 : 1)}%`
}

function toneForPct(value?: number | null) {
  if (typeof value !== 'number' || !Number.isFinite(value))
    return 'text-text-muted'
  if (value > 0.05) return 'text-gain'
  if (value < -0.05) return 'text-loss'
  return 'text-text-muted'
}

function freshnessMeta(item: WatchlistItem, userTimezone: string) {
  const quoteStatus = item.quote?.freshnessStatus ?? 'unknown'
  const quoteError = item.quote?.error
  const priceStale = item.currentScore?.price?.stale ?? false
  const timestamp =
    item.quote?.cachedAt ?? item.currentScore?.price.updatedAt ?? item.updatedAt
  const timestampMs = timestamp ? Date.parse(timestamp) : Number.NaN
  const ageMinutes = Number.isFinite(timestampMs)
    ? Math.max(0, (Date.now() - timestampMs) / 60_000)
    : null
  const scannerCurrentEnough =
    ageMinutes !== null && ageMinutes <= 15 && !priceStale
  const exactTime = timestamp
    ? formatDate(timestamp, userTimezone)
    : 'Unknown time'

  if (!item.quote || quoteError || quoteStatus === 'missing') {
    return {
      label: 'Quote issue',
      dotClass: 'bg-loss',
      textClass: 'text-loss',
      detail: quoteError
        ? `Quote error: ${quoteError}. Last update: ${exactTime}.`
        : `Quote missing. Last update: ${exactTime}.`,
    }
  }

  if (
    scannerCurrentEnough ||
    quoteStatus === 'fresh' ||
    quoteStatus === 'aging'
  ) {
    return {
      label: 'Quote OK',
      dotClass: 'bg-gain',
      textClass: 'text-gain',
      detail: `Quote current enough for this scanner. Exact update: ${exactTime}.`,
    }
  }

  if (quoteStatus === 'stale' || priceStale) {
    return {
      label: 'Stale quote',
      dotClass: 'bg-warning',
      textClass: 'text-warning',
      detail: `Quote or price-score input is stale. Last update: ${exactTime}.`,
    }
  }

  return {
    label: 'Quote unknown',
    dotClass: 'bg-warning',
    textClass: 'text-warning',
    detail: `Quote freshness unknown. Last update: ${exactTime}.`,
  }
}

// Headline tone is driven by the weighted overall-health band (and a blocking
// quote), NOT by any single partial pillar. A perpetually-missing low-weight
// pillar (e.g. options flow) would otherwise force every healthy row to a
// warning; the per-pillar partials stay visible in the expanded-row breakdown.
function dataHealthTone(item: WatchlistItem) {
  const overall = item.dataQuality?.overallPct
  const hasBlockingQuote =
    item.quote?.freshnessStatus === 'missing' || Boolean(item.quote?.error)

  if (hasBlockingQuote || (typeof overall === 'number' && overall < 50)) {
    return {
      label: overall == null ? 'Data issue' : `Data ${overall.toFixed(0)}%`,
      className: 'border-loss/30 bg-loss/10 text-loss',
      barClassName: 'bg-loss',
    }
  }

  if (overall == null || overall < 80) {
    return {
      label: overall == null ? 'Data partial' : `Data ${overall.toFixed(0)}%`,
      className: 'border-warning/30 bg-warning/10 text-warning',
      barClassName: 'bg-warning',
    }
  }

  return {
    label: `Data ${overall.toFixed(0)}%`,
    className: 'border-gain/30 bg-gain/10 text-gain',
    barClassName: 'bg-gain',
  }
}

export function FreshnessBadge({
  item,
  userTimezone,
}: {
  item: WatchlistItem
  userTimezone: string
}) {
  const meta = freshnessMeta(item, userTimezone)
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              'inline-flex cursor-help items-center gap-1.5 rounded-full border border-border/40 bg-surface/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]',
              meta.textClass,
            )}
          >
            <span className={cn('h-1.5 w-1.5 rounded-full', meta.dotClass)} />
            {meta.label}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs leading-5">
          {meta.detail}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function DataHealthBadge({
  item,
  vwapSignal,
}: {
  item: WatchlistItem
  vwapSignal?: VwapSignal | null
}) {
  const tone = dataHealthTone(item)
  const pct = Math.max(0, Math.min(100, item.dataQuality?.overallPct ?? 0))
  const pillars = Object.entries(item.dataQuality?.pillars ?? {})

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              'inline-flex min-w-[4.9rem] cursor-help flex-col gap-1 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]',
              tone.className,
            )}
          >
            <span>{tone.label}</span>
            <span className="h-1 overflow-hidden rounded-full bg-current/15">
              <span
                className={cn('block h-full rounded-full', tone.barClassName)}
                style={{ width: `${pct}%` }}
              />
            </span>
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm text-xs leading-5">
          <div className="space-y-1">
            <p className="font-semibold">Scanner data health</p>
            {pillars.map(([pillar, data]) => (
              <p key={pillar}>
                <span className="capitalize">{pillar}</span>:{' '}
                {formatPillarStatus(data.status)} · {data.details}
              </p>
            ))}
            <p>
              VWAP:{' '}
              {vwapSignal?.status === 'available' ||
              vwapSignal?.status === 'stale'
                ? `${formatPct(vwapSignal.distancePct)} vs latest session VWAP`
                : 'missing; technical score and data health are degraded'}
              {vwapSignal?.status === 'stale'
                ? ` (stale VWAP date ${vwapSignal.asOfDate ?? 'unknown'}, latest close ${vwapSignal.closeAsOfDate ?? 'unknown'})`
                : ''}
            </p>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function SetupScoreMeter({
  item,
  showLabel = true,
}: {
  item: WatchlistItem
  showLabel?: boolean
}) {
  const score = item.currentScore
  if (!score) return <span className="text-text-muted">—</span>

  const overallPct = Math.max(0, Math.min(100, score.overall ?? 0))
  const overall = roundScore(score.overall)
  const priceScore = roundScore(score.price?.score)
  const technicalScore = roundScore(score.technical?.score)
  const stale = score.price?.stale || score.technical?.stale

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="inline-flex min-w-[6rem] cursor-help flex-col gap-1">
            <div className="flex items-center gap-1.5">
              {showLabel ? (
                <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">
                  Score
                </span>
              ) : null}
              <Badge
                variant={getScoreBadgeVariant(score.overall)}
                className="font-mono tabular-nums"
              >
                {overall}
              </Badge>
              {stale ? (
                <span
                  className="h-1.5 w-1.5 rounded-full bg-warning"
                  aria-label="Score inputs stale"
                />
              ) : null}
            </div>
            <span className="block h-1.5 overflow-hidden rounded-full bg-surface-muted">
              <span
                className={cn(
                  'block h-full rounded-full',
                  getScoreBarColor(overallPct),
                )}
                style={{ width: `${overallPct}%` }}
              />
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs leading-5">
          Scanner score {overall} (price {priceScore}, technical{' '}
          {technicalScore}). This is a scanner score, not a trade instruction.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

/**
 * Single combined data-status dot for the primary scanner row. Folds quote
 * freshness and data-health into one indicator (worst-of), with the full
 * detail kept in the expanded row. Keeps the rich tooltip so nothing is lost.
 */
export function ScannerStatusDot({
  item,
  userTimezone,
}: {
  item: WatchlistItem
  userTimezone: string
}) {
  const fresh = freshnessMeta(item, userTimezone)
  const health = dataHealthTone(item)
  const isLoss =
    fresh.dotClass === 'bg-loss' || health.barClassName === 'bg-loss'
  const isWarn =
    fresh.dotClass === 'bg-warning' || health.barClassName === 'bg-warning'
  const dotClass = isLoss ? 'bg-loss' : isWarn ? 'bg-warning' : 'bg-gain'
  const statusLabel = isLoss
    ? 'Data needs attention'
    : isWarn
      ? 'Data partial or aging'
      : 'Data healthy'
  const healthPct = item.dataQuality?.overallPct

  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="inline-flex cursor-help items-center"
            aria-label={statusLabel}
          >
            <span className={cn('h-2 w-2 rounded-full', dotClass)} />
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs space-y-1 text-xs leading-5">
          <p className="font-semibold">{statusLabel}</p>
          <p>{fresh.detail}</p>
          <p>
            Data health
            {typeof healthPct === 'number' ? ` ${healthPct.toFixed(0)}%` : ''} —
            full freshness and pillar breakdown are in the expanded row.
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

/**
 * The circle-with-exclamation indicator shown next to a symbol when its scanner
 * score swung hard recently. Backed by `item.scoreAlert` (`score_alert`), which
 * fires when the overall score moved more than 10 points versus its reading at
 * the start of the trailing 7-day window. Carries a hover tooltip so it reads as
 * "worth a look", not an unexplained warning glyph.
 */
export function ScoreAlertBadge() {
  return (
    <TooltipProvider delayDuration={120}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className="inline-flex cursor-help items-center"
            aria-label="Score changed >10 points in last 7 days"
          >
            <AlertCircle className="h-4 w-4 text-accent" />
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs leading-5">
          Scanner score moved more than 10 points over the last 7 days — worth a
          fresh look at what changed.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export function PriceTrendStrip({
  trends,
  compact = false,
}: {
  trends?: PriceTrend[]
  compact?: boolean
}) {
  const byKey = new Map((trends ?? []).map((trend) => [trend.key, trend]))
  const ordered = ['D', 'W', 'M', 'Q'].map((key) => byKey.get(key))

  return (
    <div
      className={cn(
        'flex flex-wrap gap-1.5',
        compact ? 'text-[10px]' : 'text-xs',
      )}
    >
      {ordered.map((trend, index) => {
        const key = trend?.key ?? ['D', 'W', 'M', 'Q'][index]
        const available = trend?.status === 'available'
        const label = `${key} ${available ? formatPct(trend?.returnPct) : '—'}`
        return (
          <span
            key={key}
            className={cn(
              'rounded-md border border-border/35 bg-surface-muted/25 px-1.5 py-1 font-mono font-semibold tabular-nums',
              toneForPct(trend?.returnPct),
            )}
            title={
              trend
                ? `${trend.label} return from ${trend.startDate ?? 'unknown'} to ${trend.endDate ?? 'latest'} using ${trend.endSource.replace('_', ' ')}.`
                : `${key} trend unavailable.`
            }
          >
            {label}
          </span>
        )
      })}
    </div>
  )
}

export function VwapBadge({ signal }: { signal?: VwapSignal | null }) {
  const hasValue =
    (signal?.status === 'available' || signal?.status === 'stale') &&
    typeof signal.distancePct === 'number' &&
    Number.isFinite(signal.distancePct)
  const tone =
    signal?.status === 'stale'
      ? 'text-warning'
      : hasValue
        ? toneForPct(signal.distancePct)
        : 'text-warning'
  return (
    <span
      className={cn(
        'rounded-md border border-border/35 bg-surface-muted/25 px-1.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-[0.12em]',
        tone,
      )}
      title={
        hasValue && signal?.status === 'stale'
          ? `VWAP ${signal?.vwap?.toFixed(2)} is stale (${signal?.asOfDate ?? 'unknown'} vs latest close ${signal?.closeAsOfDate ?? 'unknown'}). Scanner price is ${formatPct(signal?.distancePct)} from that VWAP.`
          : hasValue
            ? `Latest-session VWAP ${signal?.vwap?.toFixed(2)}; scanner price is ${formatPct(signal?.distancePct)} from VWAP. This is not realtime intraday VWAP.`
            : 'VWAP missing for the latest session; technical score and data health are degraded.'
      }
    >
      VWAP {hasValue ? formatPct(signal?.distancePct) : '—'}
    </span>
  )
}

export function TodayGateBadge({ gate }: { gate?: TodayGate }) {
  if (!gate) return null
  const className =
    gate.tone === 'clear'
      ? 'border-gain/30 bg-gain/10 text-gain'
      : gate.tone === 'defensive'
        ? 'border-loss/30 bg-loss/10 text-loss'
        : gate.tone === 'degraded'
          ? 'border-warning/30 bg-warning/10 text-warning'
          : 'border-warning/30 bg-warning/10 text-warning'

  return (
    <span
      className={cn(
        'rounded-md border px-1.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em]',
        className,
      )}
      title={gate.detail}
    >
      Today {gate.label}
    </span>
  )
}

export function buildTodayGate(state?: {
  state?: string | null
  alert?: { active?: boolean; reason?: string | null }
  summary?: string | null
  actionText?: string | null
  coverage?: number | null
  deploymentScore?: number | null
  macroStressScore?: number | null
  tapePressureScore?: number | null
  overallCautionScore?: number | null
  overallRead?: string | null
  primaryDriver?: string | null
  driverDetail?: string | null
}): TodayGate | undefined {
  if (!state) return undefined
  const read =
    state.overallRead ??
    (state.state === 'Calm'
      ? 'normal'
      : state.state === 'Elevated'
        ? 'defensive'
        : state.state === 'Caution'
          ? 'selective'
          : 'unavailable')
  const label =
    read === 'normal'
      ? 'Normal'
      : read === 'selective'
        ? 'Selective'
        : read === 'defensive'
          ? 'Defensive'
          : 'Unavailable'
  const degraded =
    typeof state.coverage === 'number' && Number.isFinite(state.coverage)
      ? state.coverage < 0.8
      : false
  const tone: TodayGate['tone'] =
    degraded || read === 'unavailable'
      ? 'degraded'
      : read === 'normal'
        ? 'clear'
        : read === 'defensive' || state.alert?.active
          ? 'defensive'
          : 'caution'
  const macroScore =
    state.deploymentScore ??
    (typeof state.macroStressScore === 'number'
      ? 100 - state.macroStressScore
      : null)
  const tapeScore = state.tapePressureScore
  const driver = state.primaryDriver ?? 'data_limited'
  const driverSentence =
    read === 'defensive'
      ? 'Protect capital first; scanner ideas need exceptional conviction.'
      : driver === 'tape'
        ? 'Tape is the main caution; highest-conviction buys only.'
        : driver === 'macro'
          ? 'Buying conditions are the main caution; highest-conviction buys only.'
          : driver === 'both'
            ? 'Macro and tape both call for highest-conviction buys only.'
            : driver === 'data_limited'
              ? 'Tape data is limited; use macro context and setup quality.'
              : 'No major Today caution; use normal selectivity.'

  return {
    label,
    tone,
    detail: `Macro ${roundScore(macroScore)}, tape ${roundScore(tapeScore)}. ${driverSentence}`,
  }
}

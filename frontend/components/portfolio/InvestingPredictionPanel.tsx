'use client'

import {
  ArrowDownRight,
  ArrowUpRight,
  BrainCircuit,
  Gauge,
  Minus,
  Radar,
  Sparkles,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  MarketPredictionCommitteeResponse,
  MarketPredictionHistoryResponse,
} from '@/lib/api/market'
import {
  useMarketPredictionCommittee,
  useMarketPredictionHistory,
} from '@/lib/hooks/useMarketIntelligence'
import { cn } from '@/lib/utils'

const WINDOW_OPTIONS = [1, 3, 7, 14] as const
const CANONICAL_SYMBOLS = [
  'SPY',
  'XLK',
  'XLF',
  'XLE',
  'XLV',
  'XLY',
  'XLP',
  'XLI',
  'XLU',
  'XLRE',
  'XLB',
  'XLC',
] as const
const WORKFLOW_RHYTHM = [
  {
    title: 'Morning',
    detail:
      'Read the lead call, overnight handoff, and top sector tilts before the open.',
  },
  {
    title: 'Evening',
    detail:
      'Review what changed, whether the scorecard matured, and the next-session risk.',
  },
  {
    title: 'Weekend',
    detail:
      'Use the scenario framing, weekly prep, and macro-event disclosure before the week starts.',
  },
] as const

const CANONICAL_SYMBOL_SET = new Set<string>(CANONICAL_SYMBOLS)
const FRESHNESS_ORDER: Record<string, number> = {
  fresh: 0,
  stale: 1,
  missing: 2,
}

type PredictionCall = MarketPredictionCommitteeResponse['calls'][number]
type PredictionVote = MarketPredictionCommitteeResponse['votes'][number]

type NormalizedCommitteeSummary = {
  heroHeadline: string | null
  overallBias: string | null
  headline: string | null
  marketRegimeSummary: string | null
  confidenceNote: string | null
  highestConvictionViews: string[]
  heroDisagreementLabel: string | null
  disagreementLabel: string | null
  gapCallouts: string[]
  scorecardStatusNote: string | null
}

type NormalizedSourceRow = {
  cluster: string
  weight: number | null
  freshness: string | null
  note: string | null
  trackedNotRanked: boolean
}

type ScenarioCard = {
  title: 'Bull' | 'Base' | 'Bear'
  moveText: string
  summary: string
}

type RangeState =
  | {
      kind: 'range'
      summary: string
      low: number
      high: number
      expected: number | null
      leftPct: number
      rightPct: number
      zeroPct: number | null
      pointPct: number | null
    }
  | {
      kind: 'point'
      summary: string
      point: number
      pointPct: number
      zeroPct: number | null
    }
  | {
      kind: 'pending'
      summary: string
    }

type HistoryState =
  | {
      kind: 'ready'
      label: string
      detail: string
      path: string
      points: number[]
    }
  | {
      kind: 'loading' | 'sparse' | 'error'
      label: string
      detail: string
    }

type GapCallout = {
  label: string
  status: string
  detail: string
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function formatPercent(value?: number | null, digits: number = 2) {
  if (value == null || Number.isNaN(value)) return '—'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${value.toFixed(digits)}%`
}

function formatProbability(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
}

function normalizeConfidenceScore(value?: number | null) {
  if (value == null || Number.isNaN(value)) return null
  return value > 0 && value <= 1 ? value * 100 : value
}

function formatConfidenceScore(value?: number | null) {
  const normalized = normalizeConfidenceScore(value)
  if (normalized == null) return '—'
  return `${Math.round(normalized)}/100`
}

function formatScorecardDate(value?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed)
}

function directionIcon(direction: 'bullish' | 'neutral' | 'bearish') {
  if (direction === 'bullish') return ArrowUpRight
  if (direction === 'bearish') return ArrowDownRight
  return Minus
}

function directionTone(direction: 'bullish' | 'neutral' | 'bearish') {
  if (direction === 'bullish')
    return 'text-emerald-300 border-emerald-400/20 bg-emerald-500/10'
  if (direction === 'bearish')
    return 'text-rose-300 border-rose-400/20 bg-rose-500/10'
  return 'text-amber-200 border-amber-400/20 bg-amber-500/10'
}

function humanizeLabel(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

function readString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }
  return null
}

function readStringArray(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is string =>
      typeof item === 'string' && item.trim().length > 0,
  )
}

function readRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return {}
}

function normalizeDirection(value: unknown): 'bullish' | 'neutral' | 'bearish' {
  if (value === 'bullish' || value === 'bearish' || value === 'neutral') {
    return value
  }
  return 'neutral'
}

function normalizeCommitteeSummary(
  summary: MarketPredictionCommitteeResponse['committeeSummary'] | undefined,
): NormalizedCommitteeSummary {
  const record = readRecord(summary)
  return {
    heroHeadline: readString(record.heroHeadline, record.hero_headline),
    overallBias: readString(record.overallBias, record.overall_bias),
    headline: readString(
      record.headline,
      record.overallView,
      record.overall_view,
      record.summary,
    ),
    marketRegimeSummary: readString(
      record.marketRegimeSummary,
      record.market_regime_summary,
      record.overallView,
      record.overall_view,
      record.summary,
    ),
    confidenceNote: readString(
      record.confidenceNote,
      record.confidence_note,
      record.confidence,
    ),
    highestConvictionViews: [
      ...readStringArray(record.highestConvictionViews),
      ...readStringArray(record.highest_conviction_views),
      ...readStringArray(record.highestConvictionCalls),
      ...readStringArray(record.highest_conviction_calls),
    ].filter((value, index, array) => array.indexOf(value) === index),
    heroDisagreementLabel: readString(
      record.heroDisagreementLabel,
      record.hero_disagreement_label,
    ),
    disagreementLabel: readString(
      record.disagreementLabel,
      record.disagreement_label,
    ),
    gapCallouts: [
      ...readStringArray(record.gapCallouts),
      ...readStringArray(record.gap_callouts),
    ].filter((value, index, array) => array.indexOf(value) === index),
    scorecardStatusNote: readString(
      record.scorecardStatusNote,
      record.scorecard_status_note,
    ),
  }
}

function normalizePredictionCall(call: PredictionCall | null | undefined) {
  if (!call) return null
  return {
    ...call,
    symbol: call.symbol.toUpperCase(),
    directionLabel: normalizeDirection(call.directionLabel),
    confidenceScore: normalizeConfidenceScore(call.confidenceScore),
    committeeDisagreementScore: isFiniteNumber(call.committeeDisagreementScore)
      ? clamp(call.committeeDisagreementScore, 0, 1)
      : null,
  }
}

function normalizeCalls(calls: PredictionCall[] | undefined) {
  const bySymbol = new Map<string, ReturnType<typeof normalizePredictionCall>>()
  for (const call of calls ?? []) {
    const normalized = normalizePredictionCall(call)
    if (!normalized) continue
    if (!CANONICAL_SYMBOL_SET.has(normalized.symbol)) continue
    if (!bySymbol.has(normalized.symbol)) {
      bySymbol.set(normalized.symbol, normalized)
    }
  }
  return CANONICAL_SYMBOLS.map((symbol) => bySymbol.get(symbol)).filter(
    (value): value is NonNullable<typeof value> => Boolean(value),
  )
}

function selectLeadCall(
  leadCall: MarketPredictionCommitteeResponse['leadCall'] | undefined,
  calls: ReturnType<typeof normalizeCalls>,
) {
  const normalizedLead = normalizePredictionCall(leadCall)
  if (normalizedLead?.symbol === 'SPY') {
    return normalizedLead
  }
  return calls.find((call) => call.symbol === 'SPY') ?? null
}

function normalizeVotes(
  votes: PredictionVote[] | undefined,
  symbol: string,
): PredictionVote[] {
  const seen = new Set<string>()
  const filtered: PredictionVote[] = []
  for (const vote of votes ?? []) {
    if (vote.symbol.toUpperCase() !== symbol) continue
    const seatKey = vote.seatKey?.trim()
    if (!seatKey) continue
    if (seen.has(seatKey)) continue
    seen.add(seatKey)
    filtered.push({
      ...vote,
      seatKey,
      symbol,
      directionLabel: normalizeDirection(vote.directionLabel),
      confidenceScore: normalizeConfidenceScore(vote.confidenceScore),
    })
  }
  return filtered
}

function deriveDisagreementLabel(
  leadCall: ReturnType<typeof selectLeadCall>,
  summary: NormalizedCommitteeSummary,
  votes: PredictionVote[],
) {
  const explicit = readString(
    summary.heroDisagreementLabel,
    summary.disagreementLabel,
  )
  if (explicit) return humanizeLabel(explicit)

  const numericScore = leadCall?.committeeDisagreementScore
  if (isFiniteNumber(numericScore)) {
    if (numericScore < 0.15) return 'Low disagreement'
    if (numericScore < 0.35) return 'Moderate disagreement'
    return 'High disagreement'
  }

  const uniqueDirections = new Set(votes.map((vote) => vote.directionLabel))
  if (uniqueDirections.size <= 1) return 'Low disagreement'
  if (uniqueDirections.size === 2) return 'Moderate disagreement'
  return 'High disagreement'
}

function normalizeSourceRows(
  leadCall: ReturnType<typeof selectLeadCall>,
  sourceSnapshot:
    | MarketPredictionCommitteeResponse['sourceSnapshot']
    | undefined,
) {
  const rankedRows = (leadCall?.topSourceClusters ?? [])
    .map((row) => ({
      cluster: row.cluster,
      weight: isFiniteNumber(row.weight) ? row.weight : null,
      freshness: typeof row.freshness === 'string' ? row.freshness : null,
      note: typeof row.note === 'string' ? row.note : null,
      trackedNotRanked: !isFiniteNumber(row.weight),
    }))
    .filter((row) => row.cluster)

  if (rankedRows.some((row) => row.weight != null)) {
    return rankedRows.sort((left, right) => {
      if (
        left.weight != null &&
        right.weight != null &&
        left.weight !== right.weight
      ) {
        return right.weight - left.weight
      }
      if (left.weight != null && right.weight == null) return -1
      if (left.weight == null && right.weight != null) return 1
      return humanizeLabel(left.cluster).localeCompare(
        humanizeLabel(right.cluster),
      )
    })
  }

  const snapshotClusters = readRecord(sourceSnapshot).clusters
  const clusterMap = readRecord(snapshotClusters)
  return Object.entries(clusterMap)
    .map(([cluster, payload]) => {
      const details = readRecord(payload)
      return {
        cluster,
        weight: null,
        freshness: readString(details.freshness) ?? 'unknown',
        note: null,
        trackedNotRanked: true,
      }
    })
    .sort((left, right) => {
      const leftRank = FRESHNESS_ORDER[left.freshness ?? 'unknown'] ?? 99
      const rightRank = FRESHNESS_ORDER[right.freshness ?? 'unknown'] ?? 99
      if (leftRank !== rightRank) return leftRank - rightRank
      return humanizeLabel(left.cluster).localeCompare(
        humanizeLabel(right.cluster),
      )
    })
}

function deriveScenarioCards(
  leadCall: ReturnType<typeof selectLeadCall>,
  summary: NormalizedCommitteeSummary,
): ScenarioCard[] {
  const expectedMove = leadCall?.expectedMovePct ?? null
  const upperMove = isFiniteNumber(leadCall?.confidenceBandHighPct)
    ? leadCall.confidenceBandHighPct
    : expectedMove
  const lowerMove = isFiniteNumber(leadCall?.confidenceBandLowPct)
    ? leadCall.confidenceBandLowPct
    : expectedMove
  const bearNarrative = (() => {
    if (
      summary.confidenceNote &&
      /(downside|bear|selloff|weakness|drawdown|decline|invalidation)/i.test(
        summary.confidenceNote,
      )
    ) {
      return summary.confidenceNote
    }
    return `No explicit bear narrative from committee. Lower-band reference: ${formatPercent(lowerMove)}.`
  })()

  return [
    {
      title: 'Bull',
      moveText: formatPercent(upperMove),
      summary:
        summary.highestConvictionViews[0] ??
        summary.marketRegimeSummary ??
        'Upside case anchored to the upper confidence band.',
    },
    {
      title: 'Base',
      moveText: formatPercent(expectedMove),
      summary:
        leadCall?.rationaleSummary ??
        summary.overallBias ??
        'Base case follows the current committee call.',
    },
    {
      title: 'Bear',
      moveText: formatPercent(lowerMove),
      summary: bearNarrative,
    },
  ]
}

function buildRangeState(
  leadCall: ReturnType<typeof selectLeadCall>,
): RangeState {
  const low = leadCall?.confidenceBandLowPct
  const high = leadCall?.confidenceBandHighPct
  const expected = leadCall?.expectedMovePct ?? null

  if (isFiniteNumber(low) && isFiniteNumber(high)) {
    const domainMin = Math.min(low, high, 0)
    const domainMax = Math.max(low, high, 0)
    const span = domainMax - domainMin || 1
    const left = Math.min(low, high)
    const right = Math.max(low, high)
    const leftPct = ((left - domainMin) / span) * 100
    const rightPct = ((right - domainMin) / span) * 100
    const zeroPct =
      left <= 0 && right >= 0 ? ((0 - domainMin) / span) * 100 : null
    const pointPct = isFiniteNumber(expected)
      ? ((expected - domainMin) / span) * 100
      : null

    if (low === high) {
      return {
        kind: 'point',
        summary: `Single-point band ${formatPercent(low)}`,
        point: low,
        pointPct: leftPct,
        zeroPct,
      }
    }

    return {
      kind: 'range',
      summary: `Range ${formatPercent(low)} to ${formatPercent(high)}`,
      low,
      high,
      expected,
      leftPct,
      rightPct,
      zeroPct,
      pointPct,
    }
  }

  if (isFiniteNumber(expected)) {
    return {
      kind: 'point',
      summary: `Point estimate only ${formatPercent(expected)}`,
      point: expected,
      pointPct: 50,
      zeroPct: expected === 0 ? 50 : null,
    }
  }

  return {
    kind: 'pending',
    summary: 'Pending range',
  }
}

function buildSparklinePath(values: number[]) {
  if (values.length < 2) return ''
  const width = 176
  const height = 56
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width
      const y = height - ((value - min) / span) * height
      return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`
    })
    .join(' ')
}

function buildHistoryState(
  historyData: MarketPredictionHistoryResponse | undefined,
  historyError: unknown,
  historyLoading: boolean,
): HistoryState {
  if (historyError instanceof Error) {
    return {
      kind: 'error',
      label: 'Trend unavailable',
      detail: historyError.message,
    }
  }

  if (historyLoading) {
    return {
      kind: 'loading',
      label: 'Pending',
      detail: 'Loading committee history.',
    }
  }

  const points = (historyData?.items ?? [])
    .map((item) => item.expectedMovePct)
    .filter((value): value is number => isFiniteNumber(value))

  if (points.length < 2) {
    return {
      kind: 'sparse',
      label: 'Insufficient history',
      detail:
        'Need at least two usable committee snapshots before rendering a trend.',
    }
  }

  return {
    kind: 'ready',
    label: 'Live trend',
    detail: `${points.length} snapshots across recent committee runs.`,
    path: buildSparklinePath(points),
    points,
  }
}

function buildGapCallouts({
  macroMissing,
  sourceRows,
  seatCount,
  historyState,
  scorecardPending,
  summary,
}: {
  macroMissing: boolean
  sourceRows: NormalizedSourceRow[]
  seatCount: number
  historyState: HistoryState
  scorecardPending: boolean
  summary: NormalizedCommitteeSummary
}) {
  const callouts: GapCallout[] = []

  if (macroMissing) {
    callouts.push({
      label: 'Missing macro context',
      status: 'Missing macro context',
      detail:
        'Macro calendar freshness is missing or stale, so event risk is still under-specified.',
    })
  }

  if (sourceRows.some((row) => row.trackedNotRanked)) {
    callouts.push({
      label: 'Tracked not ranked',
      status: 'Tracked not ranked',
      detail:
        'Attribution rows are being tracked, but the committee has not ranked every driver by weight yet.',
    })
  }

  if (seatCount === 0) {
    callouts.push({
      label: 'Pending committee coverage',
      status: 'Pending',
      detail:
        'Seat-level commentary will appear after the next roundtable response.',
    })
  } else if (seatCount < 3) {
    callouts.push({
      label: 'Partial committee coverage',
      status: 'Partial committee coverage',
      detail:
        'Only the currently available SPY seats are shown. Missing commentary is left blank instead of invented.',
    })
  }

  if (historyState.kind !== 'ready' || scorecardPending) {
    callouts.push({
      label: 'Insufficient history',
      status: historyState.label,
      detail:
        summary.scorecardStatusNote ??
        'Calibration and trend depth will improve after more committee calls mature.',
    })
  }

  for (const callout of summary.gapCallouts) {
    if (callouts.some((item) => item.label === callout)) continue
    callouts.push({
      label: callout,
      status: 'Live note',
      detail: callout,
    })
  }

  return callouts
}

function sortVotesForDisplay(votes: PredictionVote[]) {
  const counts = votes.reduce<Record<string, number>>((accumulator, vote) => {
    accumulator[vote.directionLabel] =
      (accumulator[vote.directionLabel] ?? 0) + 1
    return accumulator
  }, {})
  const majorityDirection = (['bullish', 'neutral', 'bearish'] as const).reduce<
    'bullish' | 'neutral' | 'bearish' | null
  >((current, direction) => {
    if (!current) return direction
    return (counts[direction] ?? 0) > (counts[current] ?? 0)
      ? direction
      : current
  }, null)

  return [...votes].sort((left, right) => {
    const leftPriority = left.directionLabel === majorityDirection ? 1 : 0
    const rightPriority = right.directionLabel === majorityDirection ? 1 : 0
    if (leftPriority !== rightPriority) return leftPriority - rightPriority
    return left.seatKey.localeCompare(right.seatKey)
  })
}

function VoteBar({ votes }: { votes: PredictionVote[] }) {
  const bullish = votes.filter(
    (vote) => vote.directionLabel === 'bullish',
  ).length
  const neutral = votes.filter(
    (vote) => vote.directionLabel === 'neutral',
  ).length
  const bearish = votes.filter(
    (vote) => vote.directionLabel === 'bearish',
  ).length
  const total = votes.length || 1

  return (
    <div className="space-y-2">
      <div className="overflow-hidden rounded-full border border-border/30 bg-white/[0.06]">
        <div className="flex h-3 w-full">
          {bullish ? (
            <div
              className="bg-emerald-400/80"
              style={{ width: `${(bullish / total) * 100}%` }}
            />
          ) : null}
          {neutral ? (
            <div
              className="bg-amber-300/80"
              style={{ width: `${(neutral / total) * 100}%` }}
            />
          ) : null}
          {bearish ? (
            <div
              className="bg-rose-400/80"
              style={{ width: `${(bearish / total) * 100}%` }}
            />
          ) : null}
        </div>
      </div>
      <p className="text-xs text-text-muted">
        {bullish} bullish · {neutral} neutral · {bearish} bearish
      </p>
    </div>
  )
}

function disagreementTone(
  label: string,
): 'success' | 'warning' | 'danger' | 'neutral' {
  if (/low/i.test(label)) return 'success'
  if (/high/i.test(label)) return 'danger'
  if (/moderate/i.test(label)) return 'warning'
  return 'neutral'
}

function StatusBadge({
  label,
  tone = 'neutral',
}: {
  label: string
  tone?: 'neutral' | 'success' | 'warning' | 'danger'
}) {
  return (
    <Badge
      variant="outline"
      className={cn(
        'border-border/40 bg-black/20 text-[10px] uppercase tracking-[0.18em] text-text-muted',
        tone === 'success' && 'border-emerald-400/20 text-emerald-200',
        tone === 'warning' && 'border-amber-400/20 text-amber-200',
        tone === 'danger' && 'border-rose-400/20 text-rose-200',
      )}
    >
      {label}
    </Badge>
  )
}

function MetricTile({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string
  value: string
  detail?: string
  icon: typeof Radar
}) {
  return (
    <div className="rounded-[20px] border border-border/30 bg-black/20 p-4">
      <div className="flex items-center gap-2 text-text-muted">
        <Icon className="h-4 w-4" />
        <span className="text-[10px] uppercase tracking-[0.18em]">{label}</span>
      </div>
      <p className="mt-3 text-2xl font-semibold text-text">{value}</p>
      {detail ? <p className="mt-2 text-xs text-text-muted">{detail}</p> : null}
    </div>
  )
}

export function InvestingPredictionPanel() {
  const [windowDays, setWindowDays] =
    useState<(typeof WINDOW_OPTIONS)[number]>(3)
  const oneDayQuery = useMarketPredictionCommittee(1)
  const threeDayQuery = useMarketPredictionCommittee(3)
  const sevenDayQuery = useMarketPredictionCommittee(7)
  const fourteenDayQuery = useMarketPredictionCommittee(14)
  const committeeQueries = {
    1: oneDayQuery,
    3: threeDayQuery,
    7: sevenDayQuery,
    14: fourteenDayQuery,
  } as const
  const selectedQuery = committeeQueries[windowDays]
  const { data, isLoading, error } = selectedQuery

  const normalizedCalls = useMemo(
    () => normalizeCalls(data?.calls),
    [data?.calls],
  )
  const leadCall = useMemo(
    () => selectLeadCall(data?.leadCall, normalizedCalls),
    [data?.leadCall, normalizedCalls],
  )
  const leadSymbol = leadCall?.symbol ?? 'SPY'
  const historyQuery = useMarketPredictionHistory(leadSymbol, windowDays, 30)

  const normalizedVotes = useMemo(
    () => normalizeVotes(data?.votes, leadSymbol),
    [data?.votes, leadSymbol],
  )
  const sectorCalls = useMemo(
    () => normalizedCalls.filter((call) => call.symbol !== 'SPY'),
    [normalizedCalls],
  )
  const committeeSummary = useMemo(
    () => normalizeCommitteeSummary(data?.committeeSummary),
    [data?.committeeSummary],
  )
  const sourceRows = useMemo(
    () => normalizeSourceRows(leadCall, data?.sourceSnapshot),
    [data?.sourceSnapshot, leadCall],
  )
  const scenarioCards = useMemo(
    () => deriveScenarioCards(leadCall, committeeSummary),
    [committeeSummary, leadCall],
  )
  const disagreementLabel = useMemo(
    () => deriveDisagreementLabel(leadCall, committeeSummary, normalizedVotes),
    [committeeSummary, leadCall, normalizedVotes],
  )
  const rangeState = useMemo(() => buildRangeState(leadCall), [leadCall])
  const historyState = useMemo(
    () =>
      buildHistoryState(
        historyQuery.data,
        historyQuery.error,
        historyQuery.isLoading,
      ),
    [historyQuery.data, historyQuery.error, historyQuery.isLoading],
  )

  const heroHeadline =
    committeeSummary.heroHeadline ??
    committeeSummary.overallBias ??
    committeeSummary.headline ??
    leadCall?.rationaleSummary ??
    'Committee call pending.'
  const supportCopy =
    committeeSummary.marketRegimeSummary ??
    committeeSummary.confidenceNote ??
    leadCall?.rationaleSummary ??
    'Waiting for fuller committee context.'

  const scorecard = data?.scorecard ?? null
  const scorecardMetrics = [
    {
      label: 'Direction hit rate',
      value:
        scorecard?.sampleSize && scorecard.directionHitRate != null
          ? `${Math.round(scorecard.directionHitRate * 100)}%`
          : 'Pending',
      icon: Radar,
    },
    {
      label: 'Move MAE',
      value:
        scorecard?.sampleSize && scorecard.moveMaePct != null
          ? formatPercent(scorecard.moveMaePct)
          : 'Pending',
      icon: Gauge,
    },
    {
      label: 'Brier score',
      value:
        scorecard?.sampleSize && scorecard.brierScore != null
          ? scorecard.brierScore.toFixed(2)
          : 'Pending',
      icon: BrainCircuit,
    },
  ]
  const scorecardPending =
    !scorecard ||
    scorecard.sampleSize === 0 ||
    [
      scorecard.directionHitRate,
      scorecard.moveMaePct,
      scorecard.brierScore,
    ].every((value) => value == null)
  const scorecardTargetDate = formatScorecardDate(data?.targetDate)
  const scorecardStatus = scorecardPending
    ? (committeeSummary.scorecardStatusNote ??
      (scorecardTargetDate
        ? `No matured ${windowDays}D committee calls yet. Current cohort targets ${scorecardTargetDate}. Scorecard populates after the first post-close evaluation.`
        : `No matured ${windowDays}D committee calls yet. Scorecard populates after the first post-close evaluation.`))
    : `Scored on ${scorecard.sampleSize} matured committee calls.`

  const sourceFallbackInUse = sourceRows.some((row) => row.trackedNotRanked)
  const macroFreshness = readString(
    readRecord(readRecord(data?.sourceSnapshot).clusters).macro_calendar &&
      readRecord(
        readRecord(readRecord(data?.sourceSnapshot).clusters).macro_calendar,
      ).freshness,
  )
  const macroMissing = macroFreshness !== 'fresh'
  const gapCallouts = useMemo(
    () =>
      buildGapCallouts({
        macroMissing,
        sourceRows,
        seatCount: normalizedVotes.length,
        historyState,
        scorecardPending,
        summary: committeeSummary,
      }),
    [
      committeeSummary,
      historyState,
      macroMissing,
      normalizedVotes.length,
      scorecardPending,
      sourceRows,
    ],
  )
  const displayVotes = useMemo(
    () => sortVotesForDisplay(normalizedVotes),
    [normalizedVotes],
  )
  const horizonCards = WINDOW_OPTIONS.map((option) => {
    const snapshotQuery = committeeQueries[option]
    const snapshotCalls = normalizeCalls(snapshotQuery.data?.calls)
    const snapshotLead = selectLeadCall(
      snapshotQuery.data?.leadCall,
      snapshotCalls,
    )
    return {
      option,
      expectedMove: formatPercent(snapshotLead?.expectedMovePct),
      probability: formatProbability(snapshotLead?.probUp),
      status: snapshotLead ? 'Live' : 'Pending',
    }
  })

  const LeadIcon = directionIcon(leadCall?.directionLabel ?? 'neutral')

  return (
    <div className="space-y-4">
      <SectionCard
        title="Market Prediction Committee"
        description="Premium committee command deck grounded in the live SPY + SPDR prediction payload."
        variant="surface"
        contentClassName="space-y-4"
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,0.95fr)]">
          <div
            data-testid="prediction-hero"
            className="relative overflow-hidden rounded-[28px] border border-primary/20 bg-[radial-gradient(circle_at_top_left,_rgba(86,190,255,0.28),_transparent_34%),radial-gradient(circle_at_bottom_right,_rgba(151,71,255,0.22),_transparent_36%),linear-gradient(145deg,rgba(8,12,20,0.98),rgba(10,18,30,0.94))] p-6 shadow-[0_0_32px_-12px_rgba(86,190,255,0.45)]"
          >
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge label="Live" tone="success" />
                    <StatusBadge label={`${windowDays}D horizon`} />
                    <StatusBadge
                      label={disagreementLabel}
                      tone={disagreementTone(disagreementLabel)}
                    />
                  </div>
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        'rounded-3xl border px-4 py-3',
                        directionTone(leadCall?.directionLabel ?? 'neutral'),
                      )}
                    >
                      <LeadIcon className="h-6 w-6" />
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold uppercase tracking-[0.26em] text-text-muted">
                        Lead market call
                      </p>
                      <div className="mt-3 flex items-end gap-3">
                        <p className="font-display text-6xl italic leading-none tracking-tight text-text md:text-7xl">
                          {leadCall?.symbol ?? 'SPY'}
                        </p>
                        <div className="pb-2">
                          <p className="text-[11px] uppercase tracking-[0.22em] text-text-muted">
                            {(
                              leadCall?.directionLabel ?? 'neutral'
                            ).toUpperCase()}
                          </p>
                          <p className="text-xs text-text-muted">
                            {windowDays} trading days · {disagreementLabel}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  {WINDOW_OPTIONS.map((option) => (
                    <Button
                      key={option}
                      type="button"
                      aria-label={`${option}D`}
                      aria-pressed={option === windowDays}
                      variant={option === windowDays ? 'default' : 'outline'}
                      size="sm"
                      className={cn(
                        'rounded-full px-4',
                        option === windowDays &&
                          'shadow-[0_0_18px_-6px] shadow-primary/45',
                      )}
                      onClick={() => setWindowDays(option)}
                    >
                      {option}D
                    </Button>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.24em] text-text-muted">
                    Expected move
                  </p>
                  <p className="mt-3 font-display text-5xl italic leading-none tracking-tight text-text md:text-6xl">
                    {formatPercent(leadCall?.expectedMovePct)}
                  </p>
                  <p className="mt-4 max-w-2xl text-lg leading-snug text-text">
                    {heroHeadline}
                  </p>
                  <p className="mt-3 max-w-2xl text-sm leading-relaxed text-text-muted">
                    {error instanceof Error
                      ? error.message
                      : isLoading
                        ? 'Building the latest committee snapshot…'
                        : supportCopy}
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                  <MetricTile
                    label="Probability up"
                    value={formatProbability(leadCall?.probUp)}
                    icon={Radar}
                  />
                  <MetricTile
                    label="Confidence"
                    value={formatConfidenceScore(leadCall?.confidenceScore)}
                    icon={Gauge}
                  />
                  <MetricTile
                    label="Disagreement"
                    value={disagreementLabel}
                    icon={BrainCircuit}
                  />
                </div>
              </div>

              <div className="rounded-[22px] border border-border/30 bg-black/20 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Vote split
                    </p>
                    <p className="mt-2 text-sm text-text-muted">
                      Committee disagreement now resolves through seat counts,
                      not prose alone.
                    </p>
                  </div>
                  <StatusBadge
                    label={disagreementLabel}
                    tone={disagreementTone(disagreementLabel)}
                  />
                </div>
                <div className="mt-4">
                  <VoteBar votes={displayVotes} />
                </div>
              </div>

              <div className="rounded-[22px] border border-border/30 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Forecast band
                    </p>
                    <p className="mt-2 text-sm text-text-muted">
                      Every horizon stays visible, even while the live hero
                      focuses on the selected committee window.
                    </p>
                  </div>
                  <StatusBadge label="Live strip" tone="success" />
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-4">
                  {horizonCards.map((card) => (
                    <div
                      key={card.option}
                      className={cn(
                        'rounded-[18px] border p-3 text-left',
                        card.option === windowDays
                          ? 'border-primary/40 bg-primary/10 shadow-[0_0_18px_-8px] shadow-primary/45'
                          : 'border-border/30 bg-white/[0.03]',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                          {card.option}D
                        </p>
                        <StatusBadge
                          label={card.status}
                          tone={card.status === 'Live' ? 'success' : 'warning'}
                        />
                      </div>
                      <p className="mt-3 text-xl font-semibold text-text">
                        {card.expectedMove}
                      </p>
                      <p className="mt-1 text-xs text-text-muted">
                        Prob up {card.probability}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-[22px] border border-border/30 bg-black/20 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.2em] text-text-muted">
                      Confidence band
                    </p>
                    <p
                      data-testid="prediction-range-summary"
                      className="mt-2 text-sm font-medium text-text"
                    >
                      {rangeState.summary}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {rangeState.kind === 'range' ? (
                      <StatusBadge label="Range" tone="success" />
                    ) : rangeState.kind === 'point' ? (
                      <StatusBadge label="Point estimate only" tone="warning" />
                    ) : (
                      <StatusBadge label="Pending" tone="warning" />
                    )}
                  </div>
                </div>
                <div className="relative mt-4 h-10 rounded-full bg-white/[0.05]">
                  {rangeState.kind === 'range' ? (
                    <>
                      {rangeState.zeroPct != null ? (
                        <div
                          className="absolute inset-y-1 my-auto w-px bg-white/35"
                          style={{ left: `${rangeState.zeroPct}%` }}
                        />
                      ) : null}
                      <div
                        className="absolute top-1/2 h-4 -translate-y-1/2 rounded-full bg-gradient-to-r from-emerald-400/70 via-cyan-300/70 to-violet-400/70 shadow-[0_0_22px_-10px_rgba(103,232,249,0.9)]"
                        style={{
                          left: `${rangeState.leftPct}%`,
                          width: `${Math.max(rangeState.rightPct - rangeState.leftPct, 6)}%`,
                        }}
                      />
                      {rangeState.pointPct != null ? (
                        <div
                          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/80 bg-white shadow-[0_0_20px_-8px_rgba(255,255,255,0.9)]"
                          style={{ left: `${rangeState.pointPct}%` }}
                        />
                      ) : null}
                    </>
                  ) : rangeState.kind === 'point' ? (
                    <>
                      {rangeState.zeroPct != null ? (
                        <div
                          className="absolute inset-y-1 my-auto w-px bg-white/35"
                          style={{ left: `${rangeState.zeroPct}%` }}
                        />
                      ) : null}
                      <div
                        className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/70 bg-cyan-200 shadow-[0_0_18px_-6px_rgba(103,232,249,0.9)]"
                        style={{ left: `${rangeState.pointPct}%` }}
                      />
                    </>
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-xs text-text-muted">
                      Waiting for a usable confidence band.
                    </div>
                  )}
                </div>
                {rangeState.kind === 'range' ? (
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-text-muted">
                    <span>{formatPercent(rangeState.low)}</span>
                    <span className="text-center">
                      Mean {formatPercent(rangeState.expected)}
                    </span>
                    <span className="text-right">
                      {formatPercent(rangeState.high)}
                    </span>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <SectionCard
            title="Committee rollup"
            description="Who agrees, who hesitates, and how truthful the room feels right now."
            variant="surface"
            className="border-primary/10 bg-[linear-gradient(165deg,rgba(11,17,28,0.96),rgba(13,19,31,0.9))]"
            contentClassName="space-y-4"
          >
            <div className="rounded-[22px] border border-border/30 bg-black/20 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-muted">
                    Room status
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {disagreementLabel}
                  </p>
                </div>
                <StatusBadge
                  label={
                    normalizedVotes.length >= 3
                      ? 'Live coverage'
                      : 'Partial committee coverage'
                  }
                  tone={normalizedVotes.length >= 3 ? 'success' : 'warning'}
                />
              </div>
              <div className="mt-4">
                <VoteBar votes={displayVotes} />
              </div>
              <p className="mt-3 text-sm leading-relaxed text-text-muted">
                {supportCopy}
              </p>
            </div>

            <div
              data-testid="prediction-seat-roster"
              className="rounded-[22px] border border-border/30 bg-black/20 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-muted">
                    Seat visibility
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {normalizedVotes.length === 0
                      ? 'Pending coverage'
                      : normalizedVotes.length < 3
                        ? 'Partial committee coverage'
                        : 'Live committee coverage'}
                  </p>
                </div>
                <StatusBadge
                  label={
                    normalizedVotes.length === 0
                      ? 'Pending'
                      : normalizedVotes.length < 3
                        ? 'Partial committee coverage'
                        : 'Live'
                  }
                  tone={
                    normalizedVotes.length === 0
                      ? 'warning'
                      : normalizedVotes.length < 3
                        ? 'warning'
                        : 'success'
                  }
                />
              </div>
              {normalizedVotes.length === 0 ? (
                <p className="mt-4 text-sm text-text-muted">
                  Seat-level commentary will appear after the next roundtable
                  response.
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  {displayVotes.map((vote) => (
                    <div
                      key={vote.seatKey}
                      className="rounded-2xl border border-border/30 bg-white/[0.03] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-text">
                            {vote.seatKey}
                          </p>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
                            {vote.modelId ?? vote.agentSlug}
                          </p>
                        </div>
                        <StatusBadge
                          label={humanizeLabel(vote.directionLabel)}
                          tone={
                            vote.directionLabel === 'bullish'
                              ? 'success'
                              : vote.directionLabel === 'bearish'
                                ? 'danger'
                                : 'warning'
                          }
                        />
                      </div>
                      <p className="mt-3 text-sm leading-relaxed text-text-muted">
                        {vote.rationaleSummary ?? 'No seat commentary yet.'}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </SectionCard>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.9fr)]">
          <div className="grid gap-4">
            <SectionCard
              title="Sector board"
              description="Canonical SPY + SPDR committee calls only."
              variant="surface"
            >
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {sectorCalls.map((call) => {
                  const Icon = directionIcon(call.directionLabel)
                  return (
                    <div
                      key={call.symbol}
                      className="rounded-[20px] border border-border/30 bg-black/20 p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-lg font-semibold text-text">
                            {call.symbol}
                          </p>
                          <p className="text-[11px] uppercase tracking-[0.18em] text-text-muted">
                            {humanizeLabel(call.directionLabel)}
                          </p>
                        </div>
                        <div
                          className={cn(
                            'rounded-xl border p-2',
                            directionTone(call.directionLabel),
                          )}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
                            Move
                          </p>
                          <p className="mt-1 text-base font-medium text-text">
                            {formatPercent(call.expectedMovePct)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
                            Prob up
                          </p>
                          <p className="mt-1 text-base font-medium text-text">
                            {formatProbability(call.probUp)}
                          </p>
                        </div>
                      </div>
                      <p className="mt-4 text-xs leading-relaxed text-text-muted">
                        {call.rationaleSummary ??
                          'Committee commentary pending.'}
                      </p>
                    </div>
                  )
                })}
              </div>
            </SectionCard>

            <SectionCard
              title="Source attribution"
              description="What actually drove the current SPY call."
              variant="surface"
            >
              <div
                data-testid="prediction-source-attribution"
                className="space-y-3"
              >
                {sourceFallbackInUse ? (
                  <div className="flex justify-end">
                    <StatusBadge label="Tracked not ranked" tone="warning" />
                  </div>
                ) : null}
                {sourceRows.map((row) => (
                  <div
                    key={row.cluster}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-[20px] border border-border/30 bg-black/20 px-4 py-3"
                  >
                    <div>
                      <p className="text-sm font-medium uppercase tracking-[0.16em] text-text">
                        {humanizeLabel(row.cluster)}
                      </p>
                      {row.weight != null ? (
                        <p className="mt-1 text-xs text-text-muted">
                          Weight {Math.round(row.weight * 100)}%
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {row.note ? <StatusBadge label={row.note} /> : null}
                      <StatusBadge
                        label={row.freshness ?? 'unknown'}
                        tone={
                          row.freshness === 'fresh'
                            ? 'success'
                            : row.freshness === 'missing'
                              ? 'danger'
                              : 'warning'
                        }
                      />
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="Scenario framing"
              description="Always derived from the live lead call and confidence band."
              variant="surface"
            >
              <div className="grid gap-3 md:grid-cols-3">
                {scenarioCards.map((card) => (
                  <div
                    key={card.title}
                    className="rounded-[20px] border border-border/30 bg-black/20 p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-semibold text-text">
                          {card.title}
                        </h3>
                        <p className="mt-1 text-2xl font-medium text-text">
                          {card.moveText}
                        </p>
                      </div>
                      <StatusBadge label="Derived" tone="warning" />
                    </div>
                    <p className="mt-4 text-sm leading-relaxed text-text-muted">
                      {card.summary}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>

          <div className="grid gap-4">
            <SectionCard
              title="Calibration + self-improvement"
              description="Real scorecard truth first, then history only when it is usable."
              variant="surface"
              contentClassName="space-y-4"
            >
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
                {scorecardMetrics.map((metric) => (
                  <MetricTile
                    key={metric.label}
                    label={metric.label}
                    value={metric.value}
                    icon={metric.icon}
                  />
                ))}
              </div>
              <div className="rounded-[20px] border border-border/30 bg-black/20 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Trend status
                    </p>
                    <p
                      data-testid="prediction-history-state"
                      className="mt-2 text-lg font-semibold text-text"
                    >
                      {historyState.label}
                    </p>
                  </div>
                  <StatusBadge
                    label={historyState.label}
                    tone={
                      historyState.kind === 'ready'
                        ? 'success'
                        : historyState.kind === 'error'
                          ? 'danger'
                          : 'warning'
                    }
                  />
                </div>
                {historyState.kind === 'ready' ? (
                  historyState.points.length < 3 ? (
                    <div className="mt-4 flex items-center gap-3">
                      {historyState.points.map((_, index) => (
                        <span
                          key={`calibration-${index}-${historyState.points.length}`}
                          className="h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_12px_-4px_rgba(103,232,249,0.9)]"
                        />
                      ))}
                      <p className="text-xs text-text-muted">
                        Awaiting third snapshot.
                      </p>
                    </div>
                  ) : (
                    <svg
                      viewBox="0 0 176 56"
                      className="mt-4 h-14 w-full"
                      aria-label="Calibration trend sparkline"
                    >
                      <path
                        d={historyState.path}
                        fill="none"
                        stroke="url(#prediction-calibration-trend)"
                        strokeWidth="3"
                        strokeLinecap="round"
                      />
                      <defs>
                        <linearGradient
                          id="prediction-calibration-trend"
                          x1="0%"
                          y1="0%"
                          x2="100%"
                          y2="0%"
                        >
                          <stop offset="0%" stopColor="rgba(94,234,212,0.9)" />
                          <stop
                            offset="100%"
                            stopColor="rgba(56,189,248,0.9)"
                          />
                        </linearGradient>
                      </defs>
                    </svg>
                  )
                ) : null}
                <p className="mt-3 text-xs text-text-muted">
                  {historyState.kind === 'ready' &&
                  historyState.points.length < 3
                    ? `${historyState.detail} Awaiting third snapshot.`
                    : historyState.detail}
                </p>
              </div>
              <p className="text-xs text-text-muted">{scorecardStatus}</p>
            </SectionCard>

            <SectionCard
              title="Workflow rhythm"
              description="Fixed product guidance, not invented telemetry."
              variant="surface"
            >
              <div className="grid gap-3">
                {WORKFLOW_RHYTHM.map((card) => (
                  <div
                    key={card.title}
                    className="rounded-[20px] border border-border/30 bg-black/20 p-4"
                  >
                    <div className="flex items-center gap-2 text-text">
                      <Sparkles className="h-4 w-4 text-cyan-300" />
                      <h3 className="text-sm font-semibold uppercase tracking-[0.16em]">
                        {card.title}
                      </h3>
                    </div>
                    <p className="mt-3 text-sm leading-relaxed text-text-muted">
                      {card.detail}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard
              title="What is missing"
              description="The surface keeps every current data gap explicit instead of smoothing it away."
              variant="surface"
            >
              <div className="grid gap-3">
                {gapCallouts.map((callout) => (
                  <div
                    key={callout.label}
                    className="rounded-[20px] border border-border/30 bg-black/20 p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="text-sm font-semibold text-text">
                        {callout.label}
                      </h3>
                      <StatusBadge label={callout.status} tone="warning" />
                    </div>
                    <p className="mt-3 text-sm leading-relaxed text-text-muted">
                      {callout.detail}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}

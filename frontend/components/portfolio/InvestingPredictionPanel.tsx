'use client'

import {
  ArrowDownRight,
  ArrowUpRight,
  BrainCircuit,
  Gauge,
  Minus,
  Radar,
  RefreshCw,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  CommitteeExecutionPath,
  CommitteeRosterMode,
  MarketPredictionCommitteeResponse,
  MarketPredictionHistoryResponse,
  MarketPredictionSeatReviewResponse,
  PredictionFreshnessState,
  PredictionSourceCluster,
  PredictionSourceFreshness,
  PredictionTruthState,
} from '@/lib/api/market-types'
import {
  useMarketPredictionCommittee,
  useMarketPredictionHistory,
  useMarketPredictionQuality,
  useMarketPredictionReview,
  useRefreshMarketPredictionCommittee,
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

const CANONICAL_SYMBOL_SET = new Set<string>(CANONICAL_SYMBOLS)
const FRESHNESS_ORDER: Record<PredictionSourceFreshness, number> = {
  fresh: 0,
  stale: 1,
  missing: 2,
  unknown: 3,
}

type PredictionCall = MarketPredictionCommitteeResponse['calls'][number]
type PredictionVote = MarketPredictionCommitteeResponse['votes'][number]
type PredictionReviewSeat =
  MarketPredictionSeatReviewResponse['seatScorecards'][number]
type SourceRow = PredictionSourceCluster

type NormalizedPredictionCall = Omit<
  PredictionCall,
  'symbol' | 'topSourceClusters'
> & {
  symbol: string
  topSourceClusters: SourceRow[]
}

type NormalizedCommitteeSummary = {
  isObject: boolean
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
  truthState: PredictionTruthState | null
  committeeRosterMode: CommitteeRosterMode | null
  committeeExecutionPath: CommitteeExecutionPath | null
  executedSeatKeys: string[]
  publicationState: string | null
  abstainReasonCodes: string[]
  baselineVoteCount: number | null
  baselineSeatWeight: number | null
}

type NormalizedSourceRow = {
  cluster: string
  weight: number | null
  freshness: PredictionSourceFreshness | null
  note: string | null
  trackedNotRanked: boolean
}

type ClusterLearningRow = {
  cluster: string
  priorWeight: number | null
  effectiveWeight: number | null
  sampleSize: number | null
  skillScore: number | null
  freshness: PredictionSourceFreshness | null
}

type TruthStateDescriptor = {
  label: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
}

type FreshnessStateDescriptor = {
  label: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
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

type CalibrationMetadata = {
  rawProbUp: number | null
  calibratedProbUp: number | null
  shrink: number | null
  sampleSize: number | null
}

type HorizonCard = {
  option: (typeof WINDOW_OPTIONS)[number]
  expectedMove: string
  expectedMoveValue: number | null
  probability: string
  status: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
  shortWindowLabel: string
  targetLabel: string
  tooltipLabel: string
  freshnessLabel: string
  freshnessTone: 'neutral' | 'success' | 'warning' | 'danger'
}

type ForecastCurveState =
  | {
      kind: 'ready'
      path: string
      zeroPct: number | null
      points: { x: number; y: number; card: HorizonCard }[]
      domainMin: number
      domainMax: number
    }
  | {
      kind: 'pending'
      detail: string
    }

type FreshnessClusterRow = {
  cluster: string
  freshness: PredictionSourceFreshness
  asOfDate: string | null
  detail: string | null
}

type NormalizedPredictionFreshness = {
  state: PredictionFreshnessState
  summary: string
  invalidated: boolean
  generatedAgeSeconds: number | null
  evaluatedAgeSeconds: number | null
  marketStatus: string | null
  marketDate: string | null
  refreshAfterSeconds: number | null
  checkedAt: string | null
  reasonCodes: string[]
  criticalClusters: FreshnessClusterRow[]
}

type ReviewStateDescriptor = {
  label: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
}

type ReviewChangeRow = {
  kind: 'seat'
  key: string
  priorWeight: number
  effectiveWeight: number
}

type NormalizedReviewState = {
  reviewState: 'live' | 'warmup' | 'degraded' | null
  generatedAt: string | null
  asOfTs: string | null
  seatScorecards: PredictionReviewSeat[]
  reviewHistory: {
    generatedAt: string | null
    asOfTs: string | null
    reviewState: 'live' | 'warmup' | 'degraded' | null
    seatScorecards: PredictionReviewSeat[]
  }[]
  driftCallouts: string[]
  topUpweighted: ReviewChangeRow[]
  topDownweighted: ReviewChangeRow[]
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

function formatTrackRecord(value?: number | null) {
  if (!isFiniteNumber(value)) return 'Not enough history'
  return `${Math.round(value * 100)}% right`
}

function formatAverageMiss(value?: number | null) {
  if (!isFiniteNumber(value)) return 'Pending'
  return formatPercent(value)
}

function formatBrier(value?: number | null) {
  if (!isFiniteNumber(value)) return 'Pending'
  return value.toFixed(3)
}

function formatSignedBrierDelta(value?: number | null) {
  if (!isFiniteNumber(value)) return 'Pending'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${value.toFixed(3)}`
}

function formatModelLabel(vote: PredictionVote) {
  return vote.modelId ?? vote.provider ?? 'Unknown model'
}

function dateOnlyOrdinal(value?: string | null) {
  if (!value) return null
  const parsed = Date.parse(`${value}T12:00:00Z`)
  return Number.isNaN(parsed) ? null : parsed
}

function driverFreshnessDescriptor(
  freshness?: PredictionSourceFreshness | null,
): FreshnessStateDescriptor {
  switch (freshness) {
    case 'fresh':
      return { label: 'Current', tone: 'success' }
    case 'stale':
      return { label: 'Old', tone: 'warning' }
    case 'missing':
      return { label: 'Missing', tone: 'danger' }
    default:
      return { label: 'Unknown', tone: 'warning' }
  }
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

function formatDateOnlyLabel(value?: string | null, includeYear = true) {
  if (!value) return null
  const parsed = new Date(`${value}T12:00:00Z`)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(includeYear ? { year: 'numeric' as const } : {}),
    timeZone: 'UTC',
  }).format(parsed)
}

function tradingDayLabel(windowDays: number) {
  return `${windowDays} trading day${windowDays === 1 ? '' : 's'}`
}

function normalizeForecastCopy(value?: string | null) {
  if (!value) return value ?? null
  return value
    .replace(/\b(\d+)D\b/g, (_match, rawDays: string) => {
      const parsed = Number(rawDays)
      return Number.isFinite(parsed) ? tradingDayLabel(parsed) : rawDays
    })
    .replace(/\bcohort\b/gi, 'forecast')
    .replace(/post-close evaluation/gi, 'scored result')
    .replace(
      /Scorecard populates after the first scored result\.?/gi,
      'It will be scored after that close.',
    )
    .replace(
      /Live scorecard truth is available, but the selected lead history still needs more usable committee snapshots\.?/gi,
      'Need more scored forecasts for a reliable trend.',
    )
    .replace(
      /Live scorecard exists, but the selected lead history still needs more usable committee snapshots\.?/gi,
      'Need more scored forecasts for a reliable trend.',
    )
    .replace(
      /(The target date has landed|Target date passed), but the scored result has not published yet\.?/gi,
      'Target date passed. Waiting for the scored result.',
    )
    .replace(
      /Prediction snapshot degraded on fetch\. Showing the latest safe fallback contract until a healthy refresh returns\.?/gi,
      'Latest refresh failed. Showing fallback data.',
    )
    .replace(
      /Legacy sparse data lacks surviving lead-call attribution, so the panel stays explicit instead of inventing detail\.?/gi,
      'Older data lacks source detail.',
    )
}

function forecastWindowLabel({
  baseDate,
  targetDate,
  windowDays,
  compact = false,
}: {
  baseDate?: string | null
  targetDate?: string | null
  windowDays: number
  compact?: boolean
}) {
  const base = formatDateOnlyLabel(baseDate, !compact)
  const target = formatDateOnlyLabel(targetDate, !compact)
  if (!base || !target) return tradingDayLabel(windowDays)
  const closeSuffix = compact ? '' : ' close'
  return `${tradingDayLabel(windowDays)}: ${base}${closeSuffix} to ${target}${closeSuffix}`
}

function targetDateLabel(targetDate?: string | null) {
  const target = formatDateOnlyLabel(targetDate)
  return target ? `Targets ${target} close` : 'Target date unavailable'
}

function formatTimestampLabel(value?: string | null) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(parsed)
}

function formatAgeLabel(value?: number | null) {
  if (value == null || Number.isNaN(value)) return 'Age unavailable'
  if (value < 60) return 'Just now'
  const days = Math.floor(value / 86_400)
  const hours = Math.floor((value % 86_400) / 3_600)
  const minutes = Math.floor((value % 3_600) / 60)
  if (days > 0) return `${days}d ${hours}h old`
  if (hours > 0) return `${hours}h ${minutes}m old`
  return `${minutes}m old`
}

function formatRefreshCountdown(value?: number | null) {
  if (value == null || Number.isNaN(value)) return 'Auto-refresh scheduled'
  if (value < 60) return '<1m'
  const hours = Math.floor(value / 3_600)
  const minutes = Math.ceil((value % 3_600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function ageSecondsFromTimestamp(
  value: string | null | undefined,
  nowMs: number,
) {
  if (!value) return null
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return null
  return Math.max(0, Math.floor((nowMs - parsed.getTime()) / 1000))
}

function formatWeightShare(value?: number | null) {
  if (value == null || Number.isNaN(value)) return '—'
  return `${Math.round(value * 100)}%`
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
    .replace(/([a-z])([A-Z])/g, '$1 $2')
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

function readNumber(...values: unknown[]) {
  for (const value of values) {
    if (isFiniteNumber(value)) return value
  }
  return null
}

function normalizeCalibrationMetadata(
  call: NormalizedPredictionCall | null,
): CalibrationMetadata | null {
  const metadata = readRecord(call?.metadata)
  const calibration = readRecord(
    metadata.probabilityCalibration ?? metadata.probability_calibration,
  )
  const rawProbUp = readNumber(calibration.rawProbUp, calibration.raw_prob_up)
  const calibratedProbUp = readNumber(
    calibration.calibratedProbUp,
    calibration.calibrated_prob_up,
  )
  const shrink = readNumber(calibration.shrink)
  const sampleSize = readNumber(calibration.sampleSize, calibration.sample_size)
  if (rawProbUp == null && calibratedProbUp == null && shrink == null) {
    return null
  }
  return { rawProbUp, calibratedProbUp, shrink, sampleSize }
}

function normalizeDirection(value: unknown): 'bullish' | 'neutral' | 'bearish' {
  if (value === 'bullish' || value === 'bearish' || value === 'neutral') {
    return value
  }
  return 'neutral'
}

function normalizeFreshness(value: unknown): PredictionSourceFreshness | null {
  if (value == null) return null
  if (value === 'fresh' || value === 'stale' || value === 'missing') {
    return value
  }
  if (typeof value === 'string' && value.trim()) {
    return 'unknown'
  }
  return null
}

function normalizeFreshnessState(
  value: unknown,
): PredictionFreshnessState | null {
  if (
    value === 'fresh' ||
    value === 'aging' ||
    value === 'stale' ||
    value === 'invalid' ||
    value === 'degraded'
  ) {
    return value
  }
  return null
}

function normalizeTruthState(value: unknown): PredictionTruthState | null {
  switch (value) {
    case 'live':
      return 'live'
    case 'pendingTarget':
    case 'pending_target':
      return 'pendingTarget'
    case 'waitingAfterClose':
    case 'waiting_after_close':
      return 'waitingAfterClose'
    case 'sparseHistory':
    case 'sparse_history':
      return 'sparseHistory'
    case 'fetchError':
    case 'fetch_error':
      return 'fetchError'
    case 'legacySparse':
    case 'legacy_sparse':
      return 'legacySparse'
    default:
      return null
  }
}

function normalizeReviewState(
  value: unknown,
): 'live' | 'warmup' | 'degraded' | null {
  if (value === 'live' || value === 'warmup' || value === 'degraded') {
    return value
  }
  return null
}

function normalizeReviewChangeRows(value: unknown): ReviewChangeRow[] {
  if (!Array.isArray(value)) return []
  const rows: ReviewChangeRow[] = []
  for (const item of value) {
    const record = readRecord(item)
    const key = readString(record.key)
    const priorWeight = record.priorWeight ?? record.prior_weight
    const effectiveWeight = record.effectiveWeight ?? record.effective_weight
    if (
      record.kind !== 'seat' ||
      !key ||
      !isFiniteNumber(priorWeight) ||
      !isFiniteNumber(effectiveWeight)
    ) {
      continue
    }
    rows.push({
      kind: 'seat',
      key,
      priorWeight,
      effectiveWeight,
    })
  }
  return rows
}

function normalizeReviewHistory(
  value: unknown,
): NormalizedReviewState['reviewHistory'] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => {
      const record = readRecord(item)
      const rawScorecards = record.seatScorecards ?? record.seat_scorecards
      return {
        generatedAt: readString(record.generatedAt, record.generated_at),
        asOfTs: readString(record.asOfTs, record.as_of_ts),
        reviewState: normalizeReviewState(
          record.reviewState ?? record.review_state,
        ),
        seatScorecards: Array.isArray(rawScorecards)
          ? (rawScorecards as PredictionReviewSeat[])
          : [],
      }
    })
    .filter((item) => item.seatScorecards.length > 0)
}

function normalizeReviewPanel(
  review: MarketPredictionSeatReviewResponse | undefined,
): NormalizedReviewState {
  const reviewSummary = readRecord(review?.reviewSummary)
  return {
    reviewState: normalizeReviewState(review?.reviewState),
    generatedAt: readString(
      reviewSummary.generatedAt,
      reviewSummary.generated_at,
      review?.asOfTs,
    ),
    asOfTs: readString(review?.asOfTs),
    seatScorecards: review?.seatScorecards ?? [],
    reviewHistory: normalizeReviewHistory(review?.reviewHistory),
    driftCallouts: [
      ...readStringArray(reviewSummary.driftCallouts),
      ...readStringArray(reviewSummary.drift_callouts),
    ].filter((value, index, array) => array.indexOf(value) === index),
    topUpweighted: normalizeReviewChangeRows(
      reviewSummary.topUpweighted ?? reviewSummary.top_upweighted,
    ),
    topDownweighted: normalizeReviewChangeRows(
      reviewSummary.topDownweighted ?? reviewSummary.top_downweighted,
    ),
  }
}

function normalizeSourceClusters(value: unknown): SourceRow[] {
  if (!Array.isArray(value)) return []

  const rows: SourceRow[] = []
  for (const entry of value) {
    const record = readRecord(entry)
    const cluster = readString(record.cluster)
    if (!cluster) continue
    rows.push({
      cluster,
      weight: isFiniteNumber(record.weight) ? record.weight : null,
      freshness: normalizeFreshness(record.freshness),
      note: readString(record.note),
    })
  }
  return rows
}

function hasSurvivingAttribution(
  call: NormalizedPredictionCall | null | undefined,
): call is NormalizedPredictionCall {
  return Boolean(call?.symbol && call.topSourceClusters.length > 0)
}

function normalizeCommitteeSummary(
  summary: MarketPredictionCommitteeResponse['committeeSummary'] | undefined,
): NormalizedCommitteeSummary {
  const isObject = Boolean(
    summary && typeof summary === 'object' && !Array.isArray(summary),
  )
  const record = readRecord(summary)
  return {
    isObject,
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
    truthState: normalizeTruthState(record.truthState ?? record.truth_state),
    committeeRosterMode:
      record.committeeRosterMode === 'defaultRoster' ||
      record.committeeRosterMode === 'default_roster'
        ? 'defaultRoster'
        : record.committeeRosterMode === 'customRoster' ||
            record.committeeRosterMode === 'custom_roster'
          ? 'customRoster'
          : record.committee_roster_mode === 'defaultRoster' ||
              record.committee_roster_mode === 'default_roster'
            ? 'defaultRoster'
            : record.committee_roster_mode === 'customRoster' ||
                record.committee_roster_mode === 'custom_roster'
              ? 'customRoster'
              : null,
    committeeExecutionPath:
      record.committeeExecutionPath === 'committeeEndpoint' ||
      record.committeeExecutionPath === 'committee_endpoint'
        ? 'committeeEndpoint'
        : record.committeeExecutionPath === 'fallbackCompletion' ||
            record.committeeExecutionPath === 'fallback_completion'
          ? 'fallbackCompletion'
          : record.committee_execution_path === 'committeeEndpoint' ||
              record.committee_execution_path === 'committee_endpoint'
            ? 'committeeEndpoint'
            : record.committee_execution_path === 'fallbackCompletion' ||
                record.committee_execution_path === 'fallback_completion'
              ? 'fallbackCompletion'
              : null,
    executedSeatKeys: [
      ...readStringArray(record.executedSeatKeys),
      ...readStringArray(record.executed_seat_keys),
    ].filter((value, index, array) => array.indexOf(value) === index),
    publicationState: readString(
      record.publicationState,
      record.publication_state,
    ),
    abstainReasonCodes: [
      ...readStringArray(record.abstainReasonCodes),
      ...readStringArray(record.abstain_reason_codes),
    ].filter((value, index, array) => array.indexOf(value) === index),
    baselineVoteCount: isFiniteNumber(record.baselineVoteCount)
      ? record.baselineVoteCount
      : isFiniteNumber(record.baseline_vote_count)
        ? record.baseline_vote_count
        : null,
    baselineSeatWeight: isFiniteNumber(record.baselineSeatWeight)
      ? record.baselineSeatWeight
      : isFiniteNumber(record.baseline_seat_weight)
        ? record.baseline_seat_weight
        : null,
  }
}

function normalizePredictionCall(
  call: PredictionCall | null | undefined,
): NormalizedPredictionCall | null {
  if (!call) return null
  return {
    ...call,
    symbol:
      typeof call.symbol === 'string' ? call.symbol.trim().toUpperCase() : '',
    directionLabel: normalizeDirection(call.directionLabel),
    confidenceScore: normalizeConfidenceScore(call.confidenceScore),
    committeeDisagreementScore: isFiniteNumber(call.committeeDisagreementScore)
      ? clamp(call.committeeDisagreementScore, 0, 1)
      : null,
    topSourceClusters: normalizeSourceClusters(call.topSourceClusters),
  }
}

function normalizeCalls(
  calls: PredictionCall[] | undefined,
  canonicalOnly: boolean = false,
) {
  const bySymbol = new Map<string, NormalizedPredictionCall>()
  for (const call of calls ?? []) {
    const normalized = normalizePredictionCall(call)
    if (!normalized?.symbol) continue
    if (canonicalOnly && !CANONICAL_SYMBOL_SET.has(normalized.symbol)) continue
    if (!bySymbol.has(normalized.symbol)) {
      bySymbol.set(normalized.symbol, normalized)
    }
  }

  if (canonicalOnly) {
    return CANONICAL_SYMBOLS.map((symbol) => bySymbol.get(symbol)).filter(
      (value): value is NormalizedPredictionCall => Boolean(value),
    )
  }

  return [...bySymbol.values()]
}

function selectDisplayLeadCall(
  leadCall: MarketPredictionCommitteeResponse['leadCall'] | undefined,
  calls: ReturnType<typeof normalizeCalls>,
) {
  const normalizedLead = normalizePredictionCall(leadCall)
  if (normalizedLead?.symbol) {
    return normalizedLead
  }
  return calls.find((call) => call.symbol === 'SPY') ?? calls[0] ?? null
}

function selectAttributedLeadCall(
  leadCall: MarketPredictionCommitteeResponse['leadCall'] | undefined,
  calls: ReturnType<typeof normalizeCalls>,
) {
  const normalizedLead = normalizePredictionCall(leadCall)
  if (hasSurvivingAttribution(normalizedLead)) {
    return normalizedLead
  }
  return (
    calls.find(
      (call) => call.symbol === 'SPY' && hasSurvivingAttribution(call),
    ) ??
    calls.find((call) => hasSurvivingAttribution(call)) ??
    null
  )
}

function normalizeVotes(
  votes: PredictionVote[] | undefined,
  symbol: string,
): PredictionVote[] {
  const seen = new Set<string>()
  const filtered: PredictionVote[] = []
  for (const vote of votes ?? []) {
    const voteSymbol =
      typeof vote.symbol === 'string' ? vote.symbol.trim().toUpperCase() : ''
    if (voteSymbol !== symbol) continue
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
      sourceClusters: normalizeSourceClusters(vote.sourceClusters),
    })
  }
  return filtered
}

function deriveDisagreementLabel(
  leadCall: ReturnType<typeof selectDisplayLeadCall>,
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
  leadCall: ReturnType<typeof selectAttributedLeadCall>,
) {
  const rankedRows = (leadCall?.topSourceClusters ?? [])
    .map((row) => ({
      cluster: row.cluster,
      weight: isFiniteNumber(row.weight) ? row.weight : null,
      freshness: normalizeFreshness(row.freshness),
      note: typeof row.note === 'string' ? row.note : null,
      trackedNotRanked: !isFiniteNumber(row.weight),
    }))
    .filter((row) => row.cluster)

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
    const leftRank = FRESHNESS_ORDER[left.freshness ?? 'unknown'] ?? 99
    const rightRank = FRESHNESS_ORDER[right.freshness ?? 'unknown'] ?? 99
    if (leftRank !== rightRank) return leftRank - rightRank
    return humanizeLabel(left.cluster).localeCompare(
      humanizeLabel(right.cluster),
    )
  })
}

function normalizeClusterLearningRows(
  sourceSnapshot:
    | MarketPredictionCommitteeResponse['sourceSnapshot']
    | undefined,
): ClusterLearningRow[] {
  const clusters = readRecord(sourceSnapshot?.clusters)
  const keys = [
    ['market_regime', 'marketRegime'],
    ['sentiment', 'sentiment'],
    ['options_positioning', 'optionsPositioning'],
    ['macro_calendar', 'macroCalendar'],
  ] as const

  return keys.map(([cluster, camelKey]) => {
    const payload = readRecord(clusters[camelKey] ?? clusters[cluster])
    const priorWeight = payload.priorWeight ?? payload.prior_weight
    const effectiveWeight = payload.effectiveWeight ?? payload.effective_weight
    const sampleSize = payload.sampleSize ?? payload.sample_size
    const skillScore = payload.skillScore ?? payload.skill_score
    return {
      cluster,
      priorWeight: isFiniteNumber(priorWeight) ? priorWeight : null,
      effectiveWeight: isFiniteNumber(effectiveWeight) ? effectiveWeight : null,
      sampleSize: isFiniteNumber(sampleSize)
        ? Math.max(0, Math.trunc(sampleSize))
        : null,
      skillScore: isFiniteNumber(skillScore) ? skillScore : null,
      freshness: normalizeFreshness(payload.freshness),
    }
  })
}

function sourceEvidenceLabel(row: NormalizedSourceRow) {
  if (row.weight != null) return `Rank ${Math.round(row.weight * 100)}%`
  if (/tracked not ranked/i.test(row.note ?? '')) {
    return 'Awaiting scored history'
  }
  return normalizeForecastCopy(row.note) ?? 'Awaiting scored history'
}

function normalizeFreshnessClusters(value: unknown): FreshnessClusterRow[] {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      const record = readRecord(entry)
      const cluster = readString(record.cluster)
      const freshness = normalizeFreshness(record.freshness) ?? 'unknown'
      if (!cluster) return null
      return {
        cluster,
        freshness,
        asOfDate: readString(record.asOfDate, record.as_of_date),
        detail: readString(record.detail),
      }
    })
    .filter((value): value is FreshnessClusterRow => Boolean(value))
}

function normalizePredictionFreshness(
  summary: MarketPredictionCommitteeResponse['freshnessSummary'] | undefined,
  truthState: PredictionTruthState,
): NormalizedPredictionFreshness {
  const record = readRecord(summary)
  const state = normalizeFreshnessState(record.state)
  if (state) {
    return {
      state,
      summary:
        readString(record.summary) ??
        'Snapshot freshness checked, but no summary arrived.',
      invalidated: Boolean(record.invalidated),
      generatedAgeSeconds: isFiniteNumber(record.generatedAgeSeconds)
        ? Math.max(0, Math.trunc(record.generatedAgeSeconds))
        : null,
      evaluatedAgeSeconds: isFiniteNumber(record.evaluatedAgeSeconds)
        ? Math.max(0, Math.trunc(record.evaluatedAgeSeconds))
        : null,
      marketStatus: readString(record.marketStatus, record.market_status),
      marketDate: readString(record.marketDate, record.market_date),
      refreshAfterSeconds: isFiniteNumber(record.refreshAfterSeconds)
        ? Math.max(0, Math.trunc(record.refreshAfterSeconds))
        : null,
      checkedAt: readString(record.checkedAt, record.checked_at),
      reasonCodes: [
        ...readStringArray(record.reasonCodes),
        ...readStringArray(record.reason_codes),
      ].filter((value, index, array) => array.indexOf(value) === index),
      criticalClusters: normalizeFreshnessClusters(
        record.criticalClusters ?? record.critical_clusters,
      ),
    }
  }

  return {
    state:
      truthState === 'fetchError'
        ? 'degraded'
        : truthState === 'waitingAfterClose'
          ? 'invalid'
          : 'fresh',
    summary:
      truthState === 'fetchError'
        ? 'Committee snapshot degraded. Auto-refreshing until a healthy run returns.'
        : truthState === 'waitingAfterClose'
          ? 'Target date passed. Refresh after evaluation publishes.'
          : 'Snapshot freshness contract unavailable.',
    invalidated:
      truthState === 'fetchError' || truthState === 'waitingAfterClose',
    generatedAgeSeconds: null,
    evaluatedAgeSeconds: null,
    marketStatus: null,
    marketDate: null,
    refreshAfterSeconds:
      truthState === 'fetchError' || truthState === 'waitingAfterClose'
        ? 60
        : 600,
    checkedAt: null,
    reasonCodes: [],
    criticalClusters: [],
  }
}

function truthStateDescriptor(
  truthState: PredictionTruthState,
): TruthStateDescriptor {
  switch (truthState) {
    case 'live':
      return { label: 'Live', tone: 'success' }
    case 'pendingTarget':
      return { label: 'Awaiting target close', tone: 'warning' }
    case 'waitingAfterClose':
      return { label: 'Waiting for score', tone: 'warning' }
    case 'sparseHistory':
      return { label: 'Limited history', tone: 'warning' }
    case 'fetchError':
      return { label: 'Refresh failed', tone: 'danger' }
    case 'legacySparse':
      return { label: 'Older data', tone: 'danger' }
    default:
      return { label: humanizeLabel(truthState), tone: 'neutral' }
  }
}

function freshnessStateDescriptor(
  state: PredictionFreshnessState,
): FreshnessStateDescriptor {
  switch (state) {
    case 'fresh':
      return { label: 'Current', tone: 'success' }
    case 'aging':
      return { label: 'Aging', tone: 'warning' }
    case 'stale':
      return { label: 'Old', tone: 'warning' }
    case 'invalid':
      return { label: 'Needs refresh', tone: 'danger' }
    case 'degraded':
      return { label: 'Degraded', tone: 'danger' }
    default:
      return { label: humanizeLabel(state), tone: 'neutral' }
  }
}

function reviewStateDescriptor(
  reviewState: 'live' | 'warmup' | 'degraded',
): ReviewStateDescriptor {
  switch (reviewState) {
    case 'live':
      return { label: 'Learning live', tone: 'success' }
    case 'warmup':
      return { label: 'Learning warming up', tone: 'warning' }
    case 'degraded':
      return { label: 'Learning degraded', tone: 'danger' }
    default:
      return { label: humanizeLabel(reviewState), tone: 'neutral' }
  }
}

function buildRangeState(
  leadCall: ReturnType<typeof selectDisplayLeadCall>,
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
        summary: `Only one estimate: ${formatPercent(low)}`,
        point: low,
        pointPct: leftPct,
        zeroPct,
      }
    }

    return {
      kind: 'range',
      summary: `Likely range: ${formatPercent(low)} to ${formatPercent(high)}`,
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
      summary: `Only one estimate: ${formatPercent(expected)}`,
      point: expected,
      pointPct: 50,
      zeroPct: expected === 0 ? 50 : null,
    }
  }

  return {
    kind: 'pending',
    summary: 'Likely range pending',
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

function seatHistoryValues(
  reviewHistory: NormalizedReviewState['reviewHistory'],
  seatKey: string,
  metric: keyof Pick<
    PredictionReviewSeat,
    'effectiveWeight' | 'directionHitRate' | 'avgConfidenceScore'
  >,
) {
  return reviewHistory
    .map((point) => {
      const seat = point.seatScorecards.find((row) => row.seatKey === seatKey)
      const value = seat?.[metric]
      if (!isFiniteNumber(value)) return null
      return metric === 'avgConfidenceScore'
        ? normalizeConfidenceScore(value)
        : value
    })
    .filter((value): value is number => isFiniteNumber(value))
}

function trendWord(values: number[], higherIsBetter = true) {
  if (values.length < 2) return 'Needs history'
  const first = values[0]
  const last = values[values.length - 1]
  const delta = last - first
  if (Math.abs(delta) < 0.01) return 'Flat'
  const improving = higherIsBetter ? delta > 0 : delta < 0
  return improving ? 'Improving' : 'Worse'
}

function trendLabel(
  values: number[],
  formatter: (value: number) => string,
  higherIsBetter = true,
) {
  if (values.length < 2) return 'Needs history'
  return `${trendWord(values, higherIsBetter)} · ${formatter(values[values.length - 1])}`
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
      detail: 'Loading past forecasts.',
    }
  }

  const points = (historyData?.items ?? [])
    .map((item) => item.expectedMovePct)
    .filter((value): value is number => isFiniteNumber(value))

  if (points.length < 2) {
    return {
      kind: 'sparse',
      label: 'Insufficient history',
      detail: 'Need two forecasts before showing a line.',
    }
  }

  return {
    kind: 'ready',
    label: 'Forecast history',
    detail: `${points.length} recent forecasts shown.`,
    path: buildSparklinePath(points),
    points,
  }
}

function buildForecastCurveState(
  horizonCards: HorizonCard[],
): ForecastCurveState {
  const usableCards = horizonCards.filter((card) =>
    isFiniteNumber(card.expectedMoveValue),
  )
  if (usableCards.length < 2) {
    return {
      kind: 'pending',
      detail: 'Need at least two forecast windows before drawing a curve.',
    }
  }

  const width = 176
  const height = 64
  const values = usableCards.map((card) => card.expectedMoveValue as number)
  const domainMin = Math.min(...values, 0)
  const domainMax = Math.max(...values, 0)
  const span = domainMax - domainMin || 1
  const points = usableCards.map((card, index) => {
    const x =
      usableCards.length === 1
        ? width / 2
        : (index / (usableCards.length - 1)) * width
    const value = card.expectedMoveValue as number
    const y = height - ((value - domainMin) / span) * height
    return { x, y, card }
  })
  const path = points
    .map((point, index) => {
      const command = index === 0 ? 'M' : 'L'
      return `${command} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`
    })
    .join(' ')
  const zeroPct =
    domainMin <= 0 && domainMax >= 0 ? ((domainMax - 0) / span) * 100 : null

  return {
    kind: 'ready',
    path,
    zeroPct,
    points,
    domainMin,
    domainMax,
  }
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

function disagreementMetricValue(label: string) {
  return label.replace(/\s+disagreement$/i, '')
}

function recommendedActionTone(
  action: string,
): 'success' | 'warning' | 'danger' | 'neutral' {
  if (action === 'upweight') return 'success'
  if (action === 'downweight') return 'danger'
  if (action === 'hold') return 'warning'
  return 'neutral'
}

function recommendedActionLabel(action: string) {
  if (action === 'upweight') return 'Trust rising'
  if (action === 'downweight') return 'Trust falling'
  return 'Trust steady'
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
      <p className="mt-3 text-xl font-semibold leading-tight text-text">
        {value}
      </p>
      {detail ? <p className="mt-2 text-xs text-text-muted">{detail}</p> : null}
    </div>
  )
}

function MiniTrend({
  label,
  values,
  formatter,
  higherIsBetter = true,
}: {
  label: string
  values: number[]
  formatter: (value: number) => string
  higherIsBetter?: boolean
}) {
  const path = buildSparklinePath(values)
  return (
    <div className="rounded-[14px] border border-border/30 bg-black/20 p-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
          {label}
        </p>
        <p className="text-[11px] text-text-muted">
          {trendLabel(values, formatter, higherIsBetter)}
        </p>
      </div>
      {path ? (
        <svg viewBox="0 0 176 56" className="mt-2 h-10 w-full">
          <path
            d={path}
            fill="none"
            stroke="rgba(103,232,249,0.92)"
            strokeLinecap="round"
            strokeWidth="3"
          />
        </svg>
      ) : (
        <div className="mt-2 h-10 rounded-xl bg-white/[0.03]" />
      )}
    </div>
  )
}

function ForecastPathPanel({
  forecastCurve,
  horizonCards,
  rangeState,
  windowDays,
  freshnessState,
  compact = false,
}: {
  forecastCurve: ForecastCurveState
  horizonCards: HorizonCard[]
  rangeState: RangeState
  windowDays: number
  freshnessState: NormalizedPredictionFreshness['state']
  compact?: boolean
}) {
  const freshnessBadge = freshnessStateDescriptor(freshnessState)

  return (
    <div
      className={cn(
        'rounded-[22px] border border-border/30 bg-black/20',
        compact ? 'p-3' : 'p-4',
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
            Forecast path
          </p>
          {compact ? null : (
            <p className="mt-2 text-sm text-text-muted">
              Expected move by target close.
            </p>
          )}
        </div>
        <StatusBadge label={freshnessBadge.label} tone={freshnessBadge.tone} />
      </div>
      <div
        className={cn(
          'relative rounded-[18px] border border-border/30 bg-white/[0.03] p-3',
          compact ? 'mt-3' : 'mt-4',
        )}
      >
        {forecastCurve.kind === 'ready' ? (
          <>
            <svg
              viewBox="0 0 176 64"
              className={cn('w-full', compact ? 'h-14' : 'h-20')}
              aria-label="Expected move across forecast windows"
            >
              {forecastCurve.zeroPct != null ? (
                <line
                  x1="0"
                  x2="176"
                  y1={`${forecastCurve.zeroPct}%`}
                  y2={`${forecastCurve.zeroPct}%`}
                  stroke="rgba(255,255,255,0.24)"
                  strokeDasharray="4 4"
                />
              ) : null}
              <path
                d={forecastCurve.path}
                fill="none"
                stroke="url(#prediction-forecast-curve)"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {forecastCurve.points.map((point) => (
                <circle
                  key={`forecast-point-${point.card.option}`}
                  cx={point.x}
                  cy={point.y}
                  r={point.card.option === windowDays ? 4.2 : 3}
                  fill={
                    point.card.option === windowDays
                      ? 'rgb(255,255,255)'
                      : 'rgb(103,232,249)'
                  }
                >
                  <title>{point.card.tooltipLabel}</title>
                </circle>
              ))}
              <defs>
                <linearGradient
                  id="prediction-forecast-curve"
                  x1="0%"
                  y1="0%"
                  x2="100%"
                  y2="0%"
                >
                  <stop offset="0%" stopColor="rgba(94,234,212,0.95)" />
                  <stop offset="100%" stopColor="rgba(56,189,248,0.95)" />
                </linearGradient>
              </defs>
            </svg>
            <div className="mt-2 flex items-center justify-between gap-2 text-[10px] uppercase tracking-[0.14em] text-text-muted">
              {forecastCurve.points.map((point) => (
                <span key={`forecast-label-${point.card.option}`}>
                  {point.card.targetLabel}
                </span>
              ))}
            </div>
          </>
        ) : (
          <p className="text-xs text-text-muted">{forecastCurve.detail}</p>
        )}
      </div>
      <div
        className={cn(
          'grid gap-2',
          compact ? 'mt-3 grid-cols-4' : 'mt-4 sm:grid-cols-4',
        )}
      >
        {horizonCards.map((card) => (
          <div
            key={card.option}
            title={card.tooltipLabel}
            className={cn(
              'rounded-[18px] border text-left',
              compact ? 'p-2' : 'p-3',
              card.option === windowDays
                ? 'border-primary/40 bg-primary/10 shadow-[0_0_18px_-8px] shadow-primary/45'
                : 'border-border/30 bg-white/[0.03]',
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                {compact ? card.targetLabel : tradingDayLabel(card.option)}
              </p>
              {compact ? null : (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {card.status !== 'Live' ? (
                    <StatusBadge label={card.status} tone={card.tone} />
                  ) : null}
                  <StatusBadge
                    label={card.freshnessLabel}
                    tone={card.freshnessTone}
                  />
                </div>
              )}
            </div>
            <p
              className={cn(
                'font-semibold text-text',
                compact ? 'mt-2 text-sm' : 'mt-3 text-xl',
              )}
            >
              {card.expectedMove}
            </p>
            {compact ? null : (
              <>
                <p className="mt-1 text-xs text-text-muted">
                  Closes higher: {card.probability}
                </p>
                <p className="mt-2 text-[11px] leading-relaxed text-text-muted">
                  {card.shortWindowLabel}
                </p>
              </>
            )}
          </div>
        ))}
      </div>

      <div className={compact ? 'mt-3' : 'mt-4'}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p
            data-testid="prediction-range-summary"
            className={cn(
              'font-medium text-text',
              compact ? 'text-xs' : 'text-sm',
            )}
          >
            {rangeState.summary}
          </p>
          {rangeState.kind === 'range' ? (
            <StatusBadge label="Likely range" tone="success" />
          ) : rangeState.kind === 'point' ? (
            <StatusBadge label="Point estimate" tone="warning" />
          ) : (
            <StatusBadge label="Range pending" tone="warning" />
          )}
        </div>
        <div className="relative mt-3 h-10 rounded-full bg-white/[0.05]">
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
              Waiting for a usable range.
            </div>
          )}
        </div>
        {rangeState.kind === 'range' ? (
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-text-muted">
            <span>{formatPercent(rangeState.low)}</span>
            <span className="text-center">
              Mean {formatPercent(rangeState.expected)}
            </span>
            <span className="text-right">{formatPercent(rangeState.high)}</span>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function useRelativeNow(stepMs: number = 30_000) {
  const [nowMs, setNowMs] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => {
      setNowMs(Date.now())
    }, stepMs)
    return () => window.clearInterval(timer)
  }, [stepMs])

  return nowMs
}

function FreshnessRail({
  freshness,
  generatedLabel,
  generatedAgeLabel,
  evaluatedLabel,
  evaluatedAgeLabel,
  sourceRows,
  clusterLearningRows,
  onRefresh,
  isRefreshing,
  refreshErrorMessage,
}: {
  freshness: NormalizedPredictionFreshness
  generatedLabel: string
  generatedAgeLabel: string
  evaluatedLabel: string
  evaluatedAgeLabel: string | null
  sourceRows: NormalizedSourceRow[]
  clusterLearningRows: ClusterLearningRow[]
  onRefresh: () => void
  isRefreshing: boolean
  refreshErrorMessage: string | null
}) {
  const freshnessBadge = freshnessStateDescriptor(freshness.state)
  const sourceByCluster = new Map(sourceRows.map((row) => [row.cluster, row]))
  const learningByCluster = new Map(
    clusterLearningRows.map((row) => [row.cluster, row]),
  )
  const coverageRows = freshness.criticalClusters.length
    ? freshness.criticalClusters
    : [
        {
          cluster: 'freshness contract',
          freshness: 'unknown' as const,
          asOfDate: null,
          detail: 'Backend has not published cluster freshness yet.',
        },
      ]
  const driverRows = coverageRows.map((cluster) => {
    const source = sourceByCluster.get(cluster.cluster)
    const learning = learningByCluster.get(cluster.cluster)
    const rawFreshness =
      normalizeFreshness(cluster.freshness) ??
      normalizeFreshness(learning?.freshness) ??
      normalizeFreshness(source?.freshness) ??
      'unknown'
    const asOfOrdinal = dateOnlyOrdinal(cluster.asOfDate)
    const marketOrdinal = dateOnlyOrdinal(freshness.marketDate)
    const freshnessValue =
      rawFreshness === 'fresh' && !cluster.asOfDate
        ? 'missing'
        : rawFreshness === 'fresh' &&
            asOfOrdinal != null &&
            marketOrdinal != null &&
            asOfOrdinal < marketOrdinal
          ? 'stale'
          : rawFreshness
    const weight = source?.weight ?? learning?.effectiveWeight
    const sampleSize = learning?.sampleSize
    const rankLabel = source
      ? sourceEvidenceLabel(source)
      : weight != null
        ? `Weight ${Math.round(weight * 100)}%`
        : sampleSize
          ? `${sampleSize} scored`
          : 'Awaiting scored history'
    return {
      cluster: cluster.cluster,
      freshness: freshnessValue,
      asOfDate: cluster.asOfDate,
      detail: cluster.detail,
      rankLabel,
      sampleSize,
    }
  })

  return (
    <div
      data-testid="prediction-freshness-rail"
      className={cn(
        'rounded-[22px] border p-4 backdrop-blur',
        freshness.invalidated
          ? 'border-rose-400/25 bg-rose-500/10 shadow-[0_0_28px_-16px_rgba(251,113,133,0.75)]'
          : 'border-cyan-400/20 bg-white/[0.04] shadow-[0_0_24px_-18px_rgba(103,232,249,0.7)]',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <div data-testid="prediction-freshness-state">
              <StatusBadge
                label={freshnessBadge.label}
                tone={freshnessBadge.tone}
              />
            </div>
            {freshness.marketStatus ? (
              <StatusBadge
                label={humanizeLabel(freshness.marketStatus)}
                tone={
                  freshness.marketStatus === 'open'
                    ? 'success'
                    : freshness.invalidated
                      ? 'danger'
                      : 'warning'
                }
              />
            ) : null}
            {freshness.invalidated ? (
              <StatusBadge label="Refresh needed" tone="danger" />
            ) : null}
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-muted">
              Data health
            </p>
            <p
              data-testid="prediction-freshness-summary"
              className="mt-2 max-w-3xl text-sm leading-relaxed text-text"
            >
              {freshness.summary}
            </p>
          </div>
        </div>
        <Button
          type="button"
          variant={freshness.invalidated ? 'default' : 'outline'}
          size="sm"
          className="rounded-full px-4"
          disabled={isRefreshing}
          onClick={onRefresh}
        >
          <RefreshCw
            className={cn('mr-2 h-4 w-4', isRefreshing && 'animate-spin')}
          />
          {isRefreshing ? 'Refreshing…' : 'Refresh now'}
        </Button>
      </div>

      {refreshErrorMessage ? (
        <div
          role="status"
          className="mt-4 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-100"
        >
          Refresh failed: {refreshErrorMessage}
        </div>
      ) : null}

      <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.25fr)]">
        <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
          <div className="rounded-[16px] border border-border/30 bg-black/20 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
              Snapshot
            </p>
            <p
              data-testid="prediction-last-generated-at"
              className="mt-1 text-sm font-medium text-text"
            >
              {generatedLabel}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">
              {generatedAgeLabel}
            </p>
          </div>
          <div className="rounded-[16px] border border-border/30 bg-black/20 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
              Evaluation
            </p>
            <p className="mt-1 text-sm font-medium text-text">
              {evaluatedLabel}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">
              {evaluatedAgeLabel ?? 'Pending'}
            </p>
          </div>
          <div className="rounded-[16px] border border-border/30 bg-black/20 px-3 py-2">
            <p className="text-[10px] uppercase tracking-[0.16em] text-text-muted">
              Refresh
            </p>
            <p className="mt-1 text-sm font-medium text-text">
              In {formatRefreshCountdown(freshness.refreshAfterSeconds)}
            </p>
            <p className="mt-0.5 text-xs text-text-muted">
              {freshness.marketDate ?? 'Next check'}
            </p>
          </div>
        </div>

        <div
          data-testid="prediction-source-attribution"
          className="grid gap-2 sm:grid-cols-3"
        >
          {driverRows.map((row) => (
            <div
              key={row.cluster}
              className="rounded-[16px] border border-border/30 bg-black/20 px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text">
                  {humanizeLabel(row.cluster)}
                </p>
                <StatusBadge
                  label={driverFreshnessDescriptor(row.freshness).label}
                  tone={driverFreshnessDescriptor(row.freshness).tone}
                />
              </div>
              <p className="mt-2 text-xs text-text">{row.rankLabel}</p>
              <p className="mt-1 text-xs text-text-muted">
                {row.asOfDate
                  ? `As of ${row.asOfDate}`
                  : (row.detail ?? 'Date missing')}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function InvestingPredictionPanel() {
  const [windowDays, setWindowDays] =
    useState<(typeof WINDOW_OPTIONS)[number]>(3)
  const nowMs = useRelativeNow()
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
  const { data, isLoading, error, isFetching } = selectedQuery
  const reviewQuery = useMarketPredictionReview(windowDays)
  const qualityQuery = useMarketPredictionQuality(windowDays)
  const refreshMutation = useRefreshMarketPredictionCommittee()

  const allCalls = useMemo(() => normalizeCalls(data?.calls), [data?.calls])
  const sectorCalls = useMemo(
    () =>
      normalizeCalls(data?.calls, true).filter((call) => call.symbol !== 'SPY'),
    [data?.calls],
  )
  const displayLeadCall = useMemo(
    () => selectDisplayLeadCall(data?.leadCall, allCalls),
    [allCalls, data?.leadCall],
  )
  const attributedLeadCall = useMemo(
    () => selectAttributedLeadCall(data?.leadCall, allCalls),
    [allCalls, data?.leadCall],
  )
  const leadCall = attributedLeadCall ?? displayLeadCall
  const leadSymbol = leadCall?.symbol ?? 'SPY'
  const historyQuery = useMarketPredictionHistory(leadSymbol, windowDays, 30)
  const reviewState = useMemo(
    () => normalizeReviewPanel(reviewQuery.data),
    [reviewQuery.data],
  )

  const normalizedVotes = useMemo(
    () => normalizeVotes(data?.votes, leadSymbol),
    [data?.votes, leadSymbol],
  )
  const committeeSummary = useMemo(
    () => normalizeCommitteeSummary(data?.committeeSummary),
    [data?.committeeSummary],
  )
  const clusterLearningRows = useMemo(
    () => normalizeClusterLearningRows(data?.sourceSnapshot),
    [data?.sourceSnapshot],
  )
  const sourceRows = useMemo(
    () => normalizeSourceRows(attributedLeadCall),
    [attributedLeadCall],
  )
  const disagreementLabel = useMemo(
    () => deriveDisagreementLabel(leadCall, committeeSummary, normalizedVotes),
    [committeeSummary, leadCall, normalizedVotes],
  )
  const rangeState = useMemo(() => buildRangeState(leadCall), [leadCall])
  const leadCalibration = useMemo(
    () => normalizeCalibrationMetadata(leadCall),
    [leadCall],
  )
  const historyState = useMemo(
    () =>
      buildHistoryState(
        historyQuery.data,
        historyQuery.error,
        historyQuery.isLoading,
      ),
    [historyQuery.data, historyQuery.error, historyQuery.isLoading],
  )
  const reviewStatusBadge =
    reviewQuery.error instanceof Error
      ? { label: 'Review unavailable', tone: 'danger' as const }
      : reviewState.reviewState
        ? reviewStateDescriptor(reviewState.reviewState)
        : reviewQuery.isLoading
          ? { label: 'Loading review', tone: 'warning' as const }
          : { label: 'Pending review', tone: 'warning' as const }

  const truthState =
    committeeSummary.truthState ??
    (attributedLeadCall && committeeSummary.isObject
      ? 'live'
      : attributedLeadCall
        ? 'live'
        : 'legacySparse')
  const truthStateBadge = truthStateDescriptor(truthState)
  const freshness = useMemo(
    () => normalizePredictionFreshness(data?.freshnessSummary, truthState),
    [data?.freshnessSummary, truthState],
  )
  const refreshErrorMessage = refreshMutation.error?.message ?? null

  const heroHeadline =
    committeeSummary.heroHeadline ??
    committeeSummary.overallBias ??
    committeeSummary.headline ??
    leadCall?.rationaleSummary ??
    'Committee call pending.'

  const scorecard = data?.scorecard ?? null
  const scorecardMetrics = [
    {
      label: 'Direction right',
      value:
        scorecard?.sampleSize && scorecard.directionHitRate != null
          ? `${Math.round(scorecard.directionHitRate * 100)}%`
          : 'Pending',
      detail: scorecard?.sampleSize
        ? `${scorecard.sampleSize} past forecasts`
        : 'Needs scored history',
      icon: Radar,
    },
    {
      label: 'Average miss',
      value:
        scorecard?.sampleSize && scorecard.moveMaePct != null
          ? formatPercent(scorecard.moveMaePct)
          : 'Pending',
      detail: 'Lower is better',
      icon: Gauge,
    },
    {
      label: 'Probability error',
      value:
        scorecard?.sampleSize && scorecard.brierScore != null
          ? scorecard.brierScore.toFixed(2)
          : 'Pending',
      detail: 'Lower is better',
      icon: BrainCircuit,
    },
  ]
  const qualityReport = qualityQuery.data ?? null
  const calibrationQuality = qualityReport?.calibration ?? null
  const noEdgeQuality = qualityReport?.noEdge ?? null
  const topSeatQuality = qualityReport?.seatSegments?.[0] ?? null
  const qualityMetrics = [
    {
      label: 'Calibration lift',
      value:
        calibrationQuality?.sampleSize &&
        isFiniteNumber(calibrationQuality.brierImprovementPct)
          ? `${Math.round(calibrationQuality.brierImprovementPct * 100)}%`
          : 'Pending',
      detail:
        calibrationQuality?.sampleSize &&
        isFiniteNumber(calibrationQuality.rawBrierScore) &&
        isFiniteNumber(calibrationQuality.calibratedBrierScore)
          ? `${formatBrier(calibrationQuality.rawBrierScore)} raw -> ${formatBrier(
              calibrationQuality.calibratedBrierScore,
            )}`
          : 'Needs calibrated outcomes',
      icon: BrainCircuit,
    },
    {
      label: 'No-edge rate',
      value:
        noEdgeQuality?.totalSampleSize &&
        isFiniteNumber(noEdgeQuality.noEdgeRate)
          ? formatProbability(noEdgeQuality.noEdgeRate)
          : 'Pending',
      detail: noEdgeQuality?.totalSampleSize
        ? `${noEdgeQuality.noEdgeSampleSize}/${noEdgeQuality.totalSampleSize} abstained`
        : 'Needs scored abstentions',
      icon: Gauge,
    },
    {
      label: 'Best seat',
      value: topSeatQuality ? humanizeLabel(topSeatQuality.key) : 'Pending',
      detail: topSeatQuality
        ? `${formatTrackRecord(topSeatQuality.metrics.directionHitRate)} · ${formatBrier(
            topSeatQuality.metrics.brierScore,
          )} Brier`
        : 'Needs vote outcomes',
      icon: Radar,
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
  const defaultStateNote = (() => {
    switch (truthState) {
      case 'pendingTarget':
        return scorecardTargetDate
          ? `This forecast targets ${scorecardTargetDate}. It will be scored after that close.`
          : `This ${tradingDayLabel(windowDays)} forecast has not reached its target close.`
      case 'waitingAfterClose':
        return 'Target date passed. Waiting for the scored result.'
      case 'sparseHistory':
        return 'Need more scored forecasts for a reliable trend.'
      case 'fetchError':
        return 'Latest refresh failed. Showing fallback data.'
      case 'legacySparse':
        return 'Older data lacks source detail.'
      default:
        return scorecardTargetDate
          ? `This forecast targets ${scorecardTargetDate}. It will be scored after that close.`
          : `No scored ${tradingDayLabel(windowDays)} forecasts yet.`
    }
  })()
  const truthStateNote =
    truthState === 'live'
      ? null
      : normalizeForecastCopy(
          committeeSummary.scorecardStatusNote ?? defaultStateNote,
        )
  const noEdgeNote =
    committeeSummary.publicationState === 'no_edge'
      ? `No high-quality edge: ${
          committeeSummary.abstainReasonCodes.length
            ? committeeSummary.abstainReasonCodes.map(humanizeLabel).join(', ')
            : 'evidence does not support a strong call'
        }.`
      : null
  const scorecardStatus =
    truthStateNote ??
    (scorecardPending
      ? normalizeForecastCopy(
          committeeSummary.scorecardStatusNote ?? defaultStateNote,
        )
      : `${scorecard.sampleSize} past forecasts scored.`)
  const reviewGeneratedLabel =
    formatTimestampLabel(reviewState.generatedAt) ?? 'Unavailable'
  const reviewAsOfLabel =
    formatTimestampLabel(reviewState.asOfTs) ?? reviewGeneratedLabel
  const committeeGeneratedLabel =
    formatTimestampLabel(data?.generatedAt) ??
    formatTimestampLabel(data?.asOfTs) ??
    'Unavailable'
  const predictionWindowLabel = forecastWindowLabel({
    baseDate: data?.baseDate,
    targetDate: data?.targetDate,
    windowDays,
  })
  const predictionTargetLabel = targetDateLabel(data?.targetDate)
  const lastEvaluatedLabel =
    formatTimestampLabel(data?.lastEvaluatedAt) ?? 'Pending'
  const generatedAgeLabel = formatAgeLabel(
    ageSecondsFromTimestamp(
      data?.generatedAt ?? data?.asOfTs ?? freshness.checkedAt,
      nowMs,
    ) ?? freshness.generatedAgeSeconds,
  )
  const evaluatedAgeLabel = data?.lastEvaluatedAt
    ? formatAgeLabel(
        ageSecondsFromTimestamp(data.lastEvaluatedAt, nowMs) ??
          freshness.evaluatedAgeSeconds,
      )
    : null
  const reviewStateNote =
    reviewQuery.error instanceof Error
      ? reviewQuery.error.message
      : reviewState.reviewState === 'live'
        ? 'Weights use past scored agent calls. More scored calls make this more reliable.'
        : reviewState.reviewState === 'degraded'
          ? 'Learning data is degraded. Treat weights cautiously.'
          : reviewState.reviewState === 'warmup'
            ? 'Not enough scored agent calls yet; weights stay equal.'
            : 'Learning starts after scored agent calls exist.'
  const displayVotes = useMemo(
    () => sortVotesForDisplay(normalizedVotes),
    [normalizedVotes],
  )
  const horizonCards = WINDOW_OPTIONS.map((option) => {
    const snapshotQuery = committeeQueries[option]
    const snapshotCalls = normalizeCalls(snapshotQuery.data?.calls)
    const snapshotAttributedLead = selectAttributedLeadCall(
      snapshotQuery.data?.leadCall,
      snapshotCalls,
    )
    const snapshotLead =
      snapshotAttributedLead ??
      selectDisplayLeadCall(snapshotQuery.data?.leadCall, snapshotCalls)
    const snapshotSummary = normalizeCommitteeSummary(
      snapshotQuery.data?.committeeSummary,
    )
    const snapshotTruthState =
      snapshotSummary.truthState ??
      (selectAttributedLeadCall(snapshotQuery.data?.leadCall, snapshotCalls)
        ? 'live'
        : 'legacySparse')
    const snapshotTruthBadge = truthStateDescriptor(snapshotTruthState)
    const snapshotFreshness = normalizePredictionFreshness(
      snapshotQuery.data?.freshnessSummary,
      snapshotTruthState,
    )
    const snapshotFreshnessBadge = freshnessStateDescriptor(
      snapshotFreshness.state,
    )
    const expectedMove = formatPercent(snapshotLead?.expectedMovePct)
    const probability = formatProbability(snapshotLead?.probUp)
    const targetLabel =
      formatDateOnlyLabel(snapshotQuery.data?.targetDate, false) ??
      tradingDayLabel(option)
    return {
      option,
      expectedMove,
      expectedMoveValue: isFiniteNumber(snapshotLead?.expectedMovePct)
        ? snapshotLead.expectedMovePct
        : null,
      probability,
      status: snapshotTruthBadge.label,
      tone: snapshotTruthBadge.tone,
      shortWindowLabel: forecastWindowLabel({
        baseDate: snapshotQuery.data?.baseDate,
        targetDate: snapshotQuery.data?.targetDate,
        windowDays: option,
        compact: true,
      }),
      targetLabel,
      tooltipLabel: `${tradingDayLabel(option)} target ${targetLabel}: ${expectedMove}, closes higher ${probability}, ${snapshotFreshnessBadge.label.toLowerCase()}`,
      freshnessLabel: snapshotFreshnessBadge.label,
      freshnessTone: snapshotFreshnessBadge.tone,
    }
  })
  const forecastCurve = buildForecastCurveState(horizonCards)

  const executedSeatKeys = committeeSummary.executedSeatKeys
  const LeadIcon = directionIcon(leadCall?.directionLabel ?? 'neutral')

  return (
    <div className="space-y-4">
      <SectionCard
        title="Market Prediction Committee"
        description="SPY and sector ETF forecasts with dated targets, freshness, and scored history."
        variant="surface"
        contentClassName="space-y-4"
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,0.95fr)]">
          <div
            data-testid="prediction-hero"
            className="relative self-start overflow-hidden rounded-[28px] border border-primary/20 bg-[linear-gradient(145deg,rgba(9,17,25,0.98),rgba(8,12,20,0.94))] p-6 shadow-[0_0_32px_-12px_rgba(86,190,255,0.45)]"
          >
            <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
            <div className="flex flex-col gap-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <div data-testid="prediction-truth-state">
                      <StatusBadge
                        label={truthStateBadge.label}
                        tone={truthStateBadge.tone}
                      />
                    </div>
                    <StatusBadge label={tradingDayLabel(windowDays)} />
                    <StatusBadge
                      label={disagreementLabel}
                      tone={disagreementTone(disagreementLabel)}
                    />
                    {committeeSummary.publicationState === 'no_edge' ? (
                      <StatusBadge label="No edge" tone="warning" />
                    ) : null}
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
                            {predictionTargetLabel}
                          </p>
                          <p className="mt-1 text-xs leading-relaxed text-text-muted">
                            Forecast {predictionWindowLabel} · made{' '}
                            {committeeGeneratedLabel}
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
                      aria-label={`${tradingDayLabel(option)} forecast`}
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
                      {tradingDayLabel(option)}
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
                  <p className="mt-4 line-clamp-3 max-w-2xl text-base leading-snug text-text">
                    {heroHeadline}
                  </p>
                  {error instanceof Error || isLoading ? (
                    <p className="mt-3 max-w-2xl text-sm leading-relaxed text-text-muted">
                      {error instanceof Error
                        ? error.message
                        : 'Building the latest committee snapshot…'}
                    </p>
                  ) : null}
                  {truthStateNote ? (
                    <p
                      data-testid="prediction-truth-note"
                      className="mt-3 max-w-2xl text-sm leading-relaxed text-amber-100/85"
                    >
                      {truthStateNote}
                    </p>
                  ) : null}
                  {noEdgeNote ? (
                    <p className="mt-3 max-w-2xl text-sm leading-relaxed text-amber-100/85">
                      {noEdgeNote}
                    </p>
                  ) : null}
                  {leadCalibration ? (
                    <p className="mt-3 max-w-2xl text-sm leading-relaxed text-cyan-100/80">
                      Calibrated probability:{' '}
                      {formatProbability(leadCalibration.rawProbUp)} raw {'->'}{' '}
                      {formatProbability(
                        leadCalibration.calibratedProbUp ?? leadCall?.probUp,
                      )}
                      {isFiniteNumber(leadCalibration.shrink)
                        ? ` with ${formatProbability(leadCalibration.shrink)} shrink`
                        : ''}
                      .
                    </p>
                  ) : null}
                </div>

                <div className="space-y-3">
                  <ForecastPathPanel
                    forecastCurve={forecastCurve}
                    horizonCards={horizonCards}
                    rangeState={rangeState}
                    windowDays={windowDays}
                    freshnessState={freshness.state}
                    compact
                  />
                  <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                    <MetricTile
                      label="Closes higher"
                      value={formatProbability(leadCall?.probUp)}
                      detail={
                        leadCalibration?.rawProbUp != null
                          ? `Raw ${formatProbability(leadCalibration.rawProbUp)} · ${predictionTargetLabel}`
                          : predictionTargetLabel
                      }
                      icon={Radar}
                    />
                    <MetricTile
                      label="Confidence"
                      value={formatConfidenceScore(leadCall?.confidenceScore)}
                      detail={
                        scorecard?.sampleSize
                          ? `${scorecard.sampleSize} scored forecasts`
                          : 'Needs scored history'
                      }
                      icon={Gauge}
                    />
                    <MetricTile
                      label="Disagreement"
                      value={disagreementMetricValue(disagreementLabel)}
                      icon={BrainCircuit}
                    />
                  </div>
                </div>
              </div>

              <FreshnessRail
                freshness={freshness}
                generatedLabel={committeeGeneratedLabel}
                generatedAgeLabel={generatedAgeLabel}
                evaluatedLabel={lastEvaluatedLabel}
                evaluatedAgeLabel={evaluatedAgeLabel}
                sourceRows={sourceRows}
                clusterLearningRows={clusterLearningRows}
                isRefreshing={Boolean(
                  refreshMutation.isPending || (isFetching && !isLoading),
                )}
                refreshErrorMessage={refreshErrorMessage}
                onRefresh={() => {
                  refreshMutation.mutate(windowDays)
                }}
              />
            </div>
          </div>

          <SectionCard
            title="Committee"
            description="Votes, models, and learned weights."
            variant="surface"
            className="border-primary/10 bg-[linear-gradient(165deg,rgba(11,17,28,0.96),rgba(13,19,31,0.9))]"
            contentClassName="space-y-4"
          >
            <div
              data-testid="prediction-seat-roster"
              className="rounded-[22px] border border-border/30 bg-black/20 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.2em] text-text-muted">
                    Votes
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    {disagreementLabel}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge
                    label={
                      normalizedVotes.length >= 3
                        ? 'Live coverage'
                        : normalizedVotes.length > 0
                          ? 'Partial coverage'
                          : 'Pending coverage'
                    }
                    tone={normalizedVotes.length >= 3 ? 'success' : 'warning'}
                  />
                  {committeeSummary.committeeRosterMode ? (
                    <StatusBadge
                      label={humanizeLabel(
                        committeeSummary.committeeRosterMode,
                      )}
                    />
                  ) : null}
                </div>
              </div>
              <div className="mt-4">
                <VoteBar votes={displayVotes} />
              </div>
              {executedSeatKeys.length ? (
                <p className="mt-3 text-xs text-text-muted">
                  Seats used: {executedSeatKeys.map(humanizeLabel).join(', ')}
                </p>
              ) : null}
              {committeeSummary.baselineVoteCount ? (
                <p className="mt-2 text-xs text-text-muted">
                  Baseline: {committeeSummary.baselineVoteCount} deterministic
                  vote
                  {committeeSummary.baselineVoteCount === 1 ? '' : 's'}
                  {committeeSummary.baselineSeatWeight != null
                    ? ` at ${formatProbability(
                        committeeSummary.baselineSeatWeight,
                      )} seat weight`
                    : ''}
                  .
                </p>
              ) : null}
              {normalizedVotes.length === 0 ? (
                <p className="mt-4 text-sm text-text-muted">
                  Agent votes pending.
                </p>
              ) : (
                <div className="mt-4 space-y-3">
                  {displayVotes.map((vote) => {
                    const tone =
                      vote.directionLabel === 'bullish'
                        ? 'success'
                        : vote.directionLabel === 'bearish'
                          ? 'danger'
                          : 'warning'
                    return (
                      <div
                        key={vote.seatKey}
                        className="rounded-2xl border border-border/30 bg-white/[0.03] p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-text">
                              {humanizeLabel(vote.seatKey)}
                            </p>
                            <p className="mt-1 break-words text-xs text-text-muted">
                              Agent: {vote.agentSlug || 'Unknown agent'}
                            </p>
                            <p className="mt-1 break-words text-xs text-text-muted">
                              Model: {formatModelLabel(vote)}
                            </p>
                          </div>
                          <StatusBadge
                            label={humanizeLabel(vote.directionLabel)}
                            tone={tone}
                          />
                        </div>
                        <div className="mt-4 grid grid-cols-3 gap-2">
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Move
                            </p>
                            <p className="mt-1 text-sm font-semibold text-text">
                              {formatPercent(vote.expectedMovePct)}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Higher
                            </p>
                            <p className="mt-1 text-sm font-semibold text-text">
                              {formatProbability(vote.probUp)}
                            </p>
                          </div>
                          <div>
                            <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                              Confidence
                            </p>
                            <p className="mt-1 text-sm font-semibold text-text">
                              {formatConfidenceScore(vote.confidenceScore)}
                            </p>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div
              data-testid="prediction-review-panel"
              className="rounded-[22px] border border-border/30 bg-black/20 p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                    Learning track record
                  </p>
                  <p className="mt-2 text-lg font-semibold text-text">
                    Agent trust weights
                  </p>
                  <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-muted">
                    {reviewStateNote}
                  </p>
                  <p className="mt-2 text-xs text-text-muted">
                    Updated {reviewGeneratedLabel} · Scores through{' '}
                    {reviewAsOfLabel}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <StatusBadge
                    label={reviewStatusBadge.label}
                    tone={reviewStatusBadge.tone}
                  />
                  <StatusBadge label={tradingDayLabel(windowDays)} />
                </div>
              </div>

              <div
                data-testid="prediction-review-seat-weights"
                className="mt-4 grid gap-3"
              >
                {reviewState.seatScorecards.map((seat) => {
                  const weightValues = seatHistoryValues(
                    reviewState.reviewHistory,
                    seat.seatKey,
                    'effectiveWeight',
                  )
                  const confidenceValues = seatHistoryValues(
                    reviewState.reviewHistory,
                    seat.seatKey,
                    'avgConfidenceScore',
                  )
                  const accuracyValues = seatHistoryValues(
                    reviewState.reviewHistory,
                    seat.seatKey,
                    'directionHitRate',
                  )
                  return (
                    <div
                      key={seat.seatKey}
                      className="rounded-[18px] border border-border/30 bg-white/[0.03] p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-text">
                            {humanizeLabel(seat.seatKey)}
                          </p>
                          <p className="mt-1 text-xs text-text-muted">
                            {seat.sampleSize} scored forecast
                            {seat.sampleSize === 1 ? '' : 's'}
                          </p>
                        </div>
                        <StatusBadge
                          label={recommendedActionLabel(seat.recommendedAction)}
                          tone={recommendedActionTone(seat.recommendedAction)}
                        />
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-3">
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                            Trust weight
                          </p>
                          <p className="mt-1 text-lg font-semibold text-text">
                            {formatWeightShare(seat.effectiveWeight)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                            Accuracy
                          </p>
                          <p className="mt-1 text-lg font-semibold text-text">
                            {formatTrackRecord(seat.directionHitRate)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                            Avg miss
                          </p>
                          <p className="mt-1 text-lg font-semibold text-text">
                            {formatAverageMiss(seat.moveMaePct)}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-[0.14em] text-text-muted">
                            Avg confidence
                          </p>
                          <p className="mt-1 text-lg font-semibold text-text">
                            {formatConfidenceScore(seat.avgConfidenceScore)}
                          </p>
                        </div>
                      </div>
                      <div className="mt-4 grid gap-2 sm:grid-cols-3">
                        <MiniTrend
                          label="Trust"
                          values={weightValues}
                          formatter={formatWeightShare}
                        />
                        <MiniTrend
                          label="Confidence"
                          values={confidenceValues}
                          formatter={formatConfidenceScore}
                        />
                        <MiniTrend
                          label="Accuracy"
                          values={accuracyValues}
                          formatter={formatTrackRecord}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </SectionCard>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.9fr)]">
          <div className="grid gap-4">
            <SectionCard
              title="Sector board"
              description="Same forecast window across sector ETFs."
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
                            Closes higher
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
          </div>

          <div className="grid gap-4">
            <SectionCard
              title="Past results"
              description="Older forecasts after target dates arrived."
              variant="surface"
              contentClassName="space-y-4"
            >
              <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
                {scorecardMetrics.map((metric) => (
                  <MetricTile
                    key={metric.label}
                    label={metric.label}
                    value={metric.value}
                    detail={metric.detail}
                    icon={metric.icon}
                  />
                ))}
              </div>
              <div className="rounded-[20px] border border-border/30 bg-black/20 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Quality audit
                    </p>
                    <p className="mt-2 text-lg font-semibold text-text">
                      Calibration and abstention
                    </p>
                  </div>
                  <StatusBadge
                    label={
                      qualityReport?.overall.sampleSize
                        ? `${qualityReport.overall.sampleSize} scored`
                        : qualityQuery.isLoading
                          ? 'Loading'
                          : 'Pending'
                    }
                    tone={
                      qualityReport?.overall.sampleSize
                        ? 'success'
                        : qualityQuery.error
                          ? 'danger'
                          : 'warning'
                    }
                  />
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
                  {qualityMetrics.map((metric) => (
                    <MetricTile
                      key={metric.label}
                      label={metric.label}
                      value={metric.value}
                      detail={metric.detail}
                      icon={metric.icon}
                    />
                  ))}
                </div>
                <p className="mt-3 text-xs text-text-muted">
                  {qualityQuery.error instanceof Error
                    ? qualityQuery.error.message
                    : noEdgeQuality?.totalSampleSize
                      ? `No-edge Brier delta ${formatSignedBrierDelta(
                          noEdgeQuality.noEdgeBrierDelta,
                        )}; lower is better.`
                      : 'Quality audit starts after calibrated forecasts mature.'}
                </p>
              </div>
              <div className="rounded-[20px] border border-border/30 bg-black/20 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Expected move history
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
                        Need one more forecast for a line.
                      </p>
                    </div>
                  ) : (
                    <svg
                      viewBox="0 0 176 56"
                      className="mt-4 h-14 w-full"
                      aria-label="Expected move history sparkline"
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
                    ? `${historyState.detail} Need one more forecast for a line.`
                    : historyState.detail}
                </p>
              </div>
              <p className="text-xs text-text-muted">{scorecardStatus}</p>
            </SectionCard>
          </div>
        </div>
      </SectionCard>
    </div>
  )
}

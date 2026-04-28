'use client'

import {
  ArrowDownRight,
  ArrowUpRight,
  BrainCircuit,
  Gauge,
  Minus,
  Radar,
  RefreshCw,
  Sparkles,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { SectionCard } from '@/components/shared/SectionCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type {
  CommitteeExecutionPath,
  CommitteeRosterMode,
  MacroCalendarSourceCluster,
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
}

type NormalizedSourceRow = {
  cluster: string
  weight: number | null
  freshness: PredictionSourceFreshness | null
  note: string | null
  trackedNotRanked: boolean
}

type TruthStateDescriptor = {
  label: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
}

type FreshnessStateDescriptor = {
  label: string
  tone: 'neutral' | 'success' | 'warning' | 'danger'
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

function normalizeMacroCalendar(
  sourceSnapshot:
    | MarketPredictionCommitteeResponse['sourceSnapshot']
    | undefined,
): MacroCalendarSourceCluster {
  const clusters = readRecord(sourceSnapshot?.clusters)
  return readRecord(clusters.macroCalendar) as MacroCalendarSourceCluster
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
      return { label: 'Pending target', tone: 'warning' }
    case 'waitingAfterClose':
      return { label: 'Waiting after close', tone: 'warning' }
    case 'sparseHistory':
      return { label: 'Sparse history', tone: 'warning' }
    case 'fetchError':
      return { label: 'Fetch error', tone: 'danger' }
    case 'legacySparse':
      return { label: 'Legacy sparse data', tone: 'danger' }
    default:
      return { label: humanizeLabel(truthState), tone: 'neutral' }
  }
}

function freshnessStateDescriptor(
  state: PredictionFreshnessState,
): FreshnessStateDescriptor {
  switch (state) {
    case 'fresh':
      return { label: 'Fresh', tone: 'success' }
    case 'aging':
      return { label: 'Aging', tone: 'warning' }
    case 'stale':
      return { label: 'Stale', tone: 'warning' }
    case 'invalid':
      return { label: 'Invalidated', tone: 'danger' }
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
      return { label: 'Live review', tone: 'success' }
    case 'warmup':
      return { label: 'Warmup review', tone: 'warning' }
    case 'degraded':
      return { label: 'Degraded review', tone: 'danger' }
    default:
      return { label: humanizeLabel(reviewState), tone: 'neutral' }
  }
}

function formatMacroStatusNote(
  macroCalendar: MacroCalendarSourceCluster,
  fallback: string,
) {
  const freshness = normalizeFreshness(macroCalendar.freshness)
  if (freshness === 'fresh') return fallback

  const upcomingEventCount = isFiniteNumber(macroCalendar.upcomingEventCount)
    ? Math.max(0, Math.trunc(macroCalendar.upcomingEventCount))
    : 0
  const nextEventDate = formatScorecardDate(
    readString(macroCalendar.nextEventDate),
  )
  const reason =
    macroCalendar.reason === 'staleTable' ||
    macroCalendar.reason === 'stale_table'
      ? 'stale table coverage'
      : macroCalendar.reason === 'noFutureRows' ||
          macroCalendar.reason === 'no_future_rows'
        ? 'no future rows'
        : 'incomplete calendar coverage'
  const nextEventCopy = nextEventDate ? ` Next event ${nextEventDate}.` : ''
  return `Macro calendar is ${freshness ?? 'unknown'} (${reason}); ${upcomingEventCount} upcoming events tracked in the next 14 days.${nextEventCopy}`
}

function deriveScenarioCards(
  leadCall: ReturnType<typeof selectDisplayLeadCall>,
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
  macroStatusNote,
  sourceRows,
  seatCount,
  historyState,
  scorecardPending,
  summary,
  truthState,
}: {
  macroMissing: boolean
  macroStatusNote: string
  sourceRows: NormalizedSourceRow[]
  seatCount: number
  historyState: HistoryState
  scorecardPending: boolean
  summary: NormalizedCommitteeSummary
  truthState: PredictionTruthState
}) {
  const callouts: GapCallout[] = []

  if (macroMissing) {
    callouts.push({
      label: 'Missing macro context',
      status: 'Missing macro context',
      detail: macroStatusNote,
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

  if (
    truthState !== 'live' ||
    historyState.kind !== 'ready' ||
    scorecardPending
  ) {
    callouts.push({
      label:
        truthState === 'legacySparse'
          ? 'Legacy sparse data'
          : 'Insufficient history',
      status:
        truthState === 'legacySparse'
          ? truthStateDescriptor(truthState).label
          : historyState.label,
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

function recommendedActionTone(
  action: string,
): 'success' | 'warning' | 'danger' | 'neutral' {
  if (action === 'upweight') return 'success'
  if (action === 'downweight') return 'danger'
  if (action === 'hold') return 'warning'
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
  onRefresh,
  isRefreshing,
  refreshErrorMessage,
  gapCallouts,
}: {
  freshness: NormalizedPredictionFreshness
  generatedLabel: string
  generatedAgeLabel: string
  evaluatedLabel: string
  evaluatedAgeLabel: string | null
  onRefresh: () => void
  isRefreshing: boolean
  refreshErrorMessage: string | null
  gapCallouts: GapCallout[]
}) {
  const freshnessBadge = freshnessStateDescriptor(freshness.state)
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
        <div className="space-y-2">
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
              <StatusBadge label="Refresh required" tone="danger" />
            ) : null}
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-muted">
              Freshness + evidence
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

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <div className="rounded-[18px] border border-border/30 bg-black/20 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
            Last committee snapshot
          </p>
          <p
            data-testid="prediction-last-generated-at"
            className="mt-2 text-sm font-medium text-text"
          >
            {generatedLabel}
          </p>
          <p className="mt-1 text-xs text-text-muted">{generatedAgeLabel}</p>
        </div>
        <div className="rounded-[18px] border border-border/30 bg-black/20 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
            Last evaluation
          </p>
          <p className="mt-2 text-sm font-medium text-text">{evaluatedLabel}</p>
          <p className="mt-1 text-xs text-text-muted">
            {evaluatedAgeLabel ?? 'Evaluation pending'}
          </p>
        </div>
        <div className="rounded-[18px] border border-border/30 bg-black/20 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
            Auto refresh
          </p>
          <p className="mt-2 text-sm font-medium text-text">
            In {formatRefreshCountdown(freshness.refreshAfterSeconds)}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {freshness.marketDate
              ? `Watching ${freshness.marketDate} market date.`
              : 'Watching next freshness checkpoint.'}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="rounded-[18px] border border-border/30 bg-black/20 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
            Key evidence
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-3">
            {coverageRows.map((cluster) => (
              <div
                key={cluster.cluster}
                className="rounded-2xl border border-border/30 bg-white/[0.03] px-3 py-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text">
                    {humanizeLabel(cluster.cluster)}
                  </p>
                  <StatusBadge
                    label={humanizeLabel(cluster.freshness)}
                    tone={
                      cluster.freshness === 'fresh'
                        ? 'success'
                        : cluster.freshness === 'missing'
                          ? 'danger'
                          : 'warning'
                    }
                  />
                </div>
                <p className="mt-2 text-xs text-text-muted">
                  {cluster.asOfDate
                    ? `As of ${cluster.asOfDate}`
                    : (cluster.detail ?? 'No as-of date published.')}
                </p>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-[18px] border border-border/30 bg-black/20 p-3">
          <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
            Coverage watch
          </p>
          <div className="mt-3 space-y-2">
            {gapCallouts.length ? (
              gapCallouts.slice(0, 3).map((callout) => (
                <div
                  key={callout.label}
                  className="rounded-2xl border border-border/30 bg-white/[0.03] px-3 py-2"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-text">
                      {callout.label}
                    </p>
                    <StatusBadge label={callout.status} tone="warning" />
                  </div>
                  <p className="mt-2 text-xs text-text-muted">
                    {callout.detail}
                  </p>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
                No live evidence gaps flagged for this window.
              </div>
            )}
          </div>
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
  const macroCalendar = useMemo(
    () => normalizeMacroCalendar(data?.sourceSnapshot),
    [data?.sourceSnapshot],
  )
  const sourceRows = useMemo(
    () => normalizeSourceRows(attributedLeadCall),
    [attributedLeadCall],
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
  const defaultStateNote = (() => {
    switch (truthState) {
      case 'pendingTarget':
        return scorecardTargetDate
          ? `Current ${windowDays}D cohort targets ${scorecardTargetDate}. Scorecard populates after the first post-close evaluation.`
          : `Current ${windowDays}D cohort has not hit target yet.`
      case 'waitingAfterClose':
        return 'The target date has landed, but the post-close evaluation has not published yet.'
      case 'sparseHistory':
        return 'Live scorecard truth is available, but the selected lead history still needs more usable committee snapshots.'
      case 'fetchError':
        return 'Prediction snapshot degraded on fetch. Showing the latest safe fallback contract until a healthy refresh returns.'
      case 'legacySparse':
        return 'Legacy sparse data lacks surviving lead-call attribution, so the panel stays explicit instead of inventing detail.'
      default:
        return scorecardTargetDate
          ? `No matured ${windowDays}D committee calls yet. Current cohort targets ${scorecardTargetDate}. Scorecard populates after the first post-close evaluation.`
          : `No matured ${windowDays}D committee calls yet. Scorecard populates after the first post-close evaluation.`
    }
  })()
  const truthStateNote =
    truthState === 'live'
      ? null
      : (committeeSummary.scorecardStatusNote ?? defaultStateNote)
  const scorecardStatus =
    truthStateNote ??
    (scorecardPending
      ? (committeeSummary.scorecardStatusNote ?? defaultStateNote)
      : `Scored on ${scorecard.sampleSize} matured committee calls.`)
  const reviewGeneratedLabel =
    formatTimestampLabel(reviewState.generatedAt) ?? 'Unavailable'
  const reviewAsOfLabel =
    formatTimestampLabel(reviewState.asOfTs) ?? reviewGeneratedLabel
  const committeeGeneratedLabel =
    formatTimestampLabel(data?.generatedAt) ??
    formatTimestampLabel(data?.asOfTs) ??
    'Unavailable'
  const predictionWindowLabel =
    data?.baseDate && data?.targetDate
      ? `${data.baseDate} to ${data.targetDate}`
      : `${windowDays} trading days`
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
  const reviewTimestampDiverged =
    Boolean(reviewState.generatedAt) &&
    Boolean(data?.generatedAt) &&
    reviewState.generatedAt !== data?.generatedAt
  const reviewStateNote =
    reviewQuery.error instanceof Error
      ? reviewQuery.error.message
      : reviewState.reviewState === 'live'
        ? 'Resolved seat weights are coming from matured vote cohorts.'
        : reviewState.reviewState === 'degraded'
          ? 'Review artifact degraded. Keep weights visible, but do not over-trust drift.'
          : reviewState.reviewState === 'warmup'
            ? 'Warmup artifact is holding prior weights until enough matured votes arrive.'
            : 'Review artifact will appear after the next persisted seat-weighting pass.'
  const reviewDriftSummary =
    reviewState.topUpweighted.length || reviewState.topDownweighted.length
      ? `${reviewState.topUpweighted.length} upweighted · ${reviewState.topDownweighted.length} downweighted`
      : 'No resolved drift yet'

  const sourceFallbackInUse = sourceRows.some((row) => row.trackedNotRanked)
  const macroFreshness = normalizeFreshness(macroCalendar.freshness)
  const macroMissing = macroFreshness !== 'fresh'
  const macroStatusNote = formatMacroStatusNote(
    macroCalendar,
    'Macro calendar is fresh enough for this committee snapshot.',
  )
  const gapCallouts = useMemo(
    () =>
      buildGapCallouts({
        macroMissing,
        macroStatusNote,
        sourceRows,
        seatCount: normalizedVotes.length,
        historyState,
        scorecardPending,
        summary: committeeSummary,
        truthState,
      }),
    [
      committeeSummary,
      historyState,
      macroMissing,
      macroStatusNote,
      normalizedVotes.length,
      scorecardPending,
      sourceRows,
      truthState,
    ],
  )
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
    return {
      option,
      expectedMove: formatPercent(snapshotLead?.expectedMovePct),
      probability: formatProbability(snapshotLead?.probUp),
      status: snapshotTruthBadge.label,
      tone: snapshotTruthBadge.tone,
    }
  })

  const executedSeatKeys = committeeSummary.executedSeatKeys
  const provenanceSummary = [
    `Prediction window ${predictionWindowLabel}`,
    committeeGeneratedLabel !== 'Unavailable'
      ? `As of ${committeeGeneratedLabel}`
      : null,
    committeeSummary.committeeRosterMode
      ? humanizeLabel(committeeSummary.committeeRosterMode)
      : null,
    committeeSummary.committeeExecutionPath
      ? humanizeLabel(committeeSummary.committeeExecutionPath)
      : null,
    executedSeatKeys.length ? `Seats ${executedSeatKeys.join(', ')}` : null,
  ]
    .filter((value): value is string => Boolean(value))
    .join(' · ')
  const sourceEmptyStateCopy =
    truthState === 'legacySparse'
      ? 'Legacy sparse data lacks surviving lead-call attribution.'
      : truthState === 'fetchError'
        ? 'Source attribution is unavailable on the degraded fetch fallback.'
        : 'Source attribution will appear when the selected lead call carries surviving cluster evidence.'

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
                    <div data-testid="prediction-truth-state">
                      <StatusBadge
                        label={truthStateBadge.label}
                        tone={truthStateBadge.tone}
                      />
                    </div>
                    <StatusBadge label={`${windowDays}D horizon`} />
                    <StatusBadge
                      label={disagreementLabel}
                      tone={disagreementTone(disagreementLabel)}
                    />
                    {committeeSummary.committeeExecutionPath ? (
                      <StatusBadge
                        label={humanizeLabel(
                          committeeSummary.committeeExecutionPath,
                        )}
                      />
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
                            {windowDays} trading days · {disagreementLabel}
                          </p>
                          <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-text-muted">
                            Prediction window {predictionWindowLabel} · as of{' '}
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
                  {truthStateNote ? (
                    <p
                      data-testid="prediction-truth-note"
                      className="mt-3 max-w-2xl text-sm leading-relaxed text-amber-100/85"
                    >
                      {truthStateNote}
                    </p>
                  ) : null}
                  {provenanceSummary ? (
                    <p
                      data-testid="prediction-provenance"
                      className="mt-3 max-w-2xl text-xs uppercase tracking-[0.18em] text-text-muted"
                    >
                      {provenanceSummary}
                    </p>
                  ) : null}
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

              <FreshnessRail
                freshness={freshness}
                generatedLabel={committeeGeneratedLabel}
                generatedAgeLabel={generatedAgeLabel}
                evaluatedLabel={lastEvaluatedLabel}
                evaluatedAgeLabel={evaluatedAgeLabel}
                isRefreshing={Boolean(
                  refreshMutation.isPending || (isFetching && !isLoading),
                )}
                refreshErrorMessage={refreshErrorMessage}
                onRefresh={() => {
                  refreshMutation.mutate(windowDays)
                }}
                gapCallouts={gapCallouts}
              />

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
                        <StatusBadge label={card.status} tone={card.tone} />
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
                <div className="flex flex-wrap gap-2">
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
                  {committeeSummary.committeeRosterMode ? (
                    <StatusBadge
                      label={humanizeLabel(
                        committeeSummary.committeeRosterMode,
                      )}
                    />
                  ) : null}
                  {committeeSummary.committeeExecutionPath ? (
                    <StatusBadge
                      label={humanizeLabel(
                        committeeSummary.committeeExecutionPath,
                      )}
                    />
                  ) : null}
                </div>
              </div>
              {executedSeatKeys.length ? (
                <p className="mt-4 text-xs uppercase tracking-[0.18em] text-text-muted">
                  Executed seats: {executedSeatKeys.join(', ')}
                </p>
              ) : null}
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
                {sourceRows.length === 0 ? (
                  <div className="rounded-[20px] border border-border/30 bg-black/20 px-4 py-3 text-sm text-text-muted">
                    {sourceEmptyStateCopy}
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
              title="Review artifact"
              description="Seat-weight review stays read-only and keeps its own timestamp apart from the committee snapshot."
              variant="surface"
              contentClassName="space-y-4"
            >
              <div
                data-testid="prediction-review-panel"
                className="rounded-[20px] border border-border/30 bg-black/20 p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Review state
                    </p>
                    <p className="mt-2 text-lg font-semibold text-text">
                      {reviewStatusBadge.label}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <StatusBadge
                      label={reviewStatusBadge.label}
                      tone={reviewStatusBadge.tone}
                    />
                    <StatusBadge label={`${windowDays}D horizon`} />
                    <StatusBadge
                      label={
                        reviewTimestampDiverged
                          ? 'Separate timestamps'
                          : 'Synced timestamps'
                      }
                      tone={reviewTimestampDiverged ? 'warning' : 'success'}
                    />
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <div className="rounded-[18px] border border-border/30 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Review artifact
                    </p>
                    <p
                      data-testid="prediction-review-generated-at"
                      className="mt-2 text-sm font-medium text-text"
                    >
                      {reviewGeneratedLabel}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      As of {reviewAsOfLabel}
                    </p>
                  </div>
                  <div className="rounded-[18px] border border-border/30 bg-white/[0.03] p-3">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-text-muted">
                      Committee snapshot
                    </p>
                    <p
                      data-testid="prediction-committee-generated-at"
                      className="mt-2 text-sm font-medium text-text"
                    >
                      {committeeGeneratedLabel}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      {reviewDriftSummary}
                    </p>
                  </div>
                </div>

                <p className="mt-4 text-sm leading-relaxed text-text-muted">
                  {reviewStateNote}
                </p>

                <div
                  data-testid="prediction-review-seat-weights"
                  className="mt-4 grid gap-3 md:grid-cols-3"
                >
                  {reviewState.seatScorecards.map((seat) => (
                    <div
                      key={seat.seatKey}
                      className="rounded-[18px] border border-border/30 bg-white/[0.03] p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-text">
                            {humanizeLabel(seat.seatKey)}
                          </p>
                          <p className="mt-1 text-[11px] uppercase tracking-[0.16em] text-text-muted">
                            Prior {formatWeightShare(seat.priorWeight)} ·{' '}
                            {seat.sampleSize} matured vote
                            {seat.sampleSize === 1 ? '' : 's'}
                          </p>
                        </div>
                        <StatusBadge
                          label={humanizeLabel(seat.recommendedAction)}
                          tone={recommendedActionTone(seat.recommendedAction)}
                        />
                      </div>
                      <p className="mt-3 text-2xl font-semibold text-text">
                        {formatWeightShare(seat.effectiveWeight)}
                      </p>
                      <p className="mt-1 text-xs text-text-muted">
                        Effective weight
                      </p>
                    </div>
                  ))}
                </div>

                {reviewState.driftCallouts.length > 0 ? (
                  <div className="mt-4 space-y-2">
                    {reviewState.driftCallouts.map((callout) => (
                      <div
                        key={callout}
                        className="rounded-[16px] border border-border/30 bg-white/[0.03] px-3 py-2 text-xs text-text-muted"
                      >
                        {callout}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </SectionCard>

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

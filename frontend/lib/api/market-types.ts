/**
 * Shared TypeScript types for Market data API
 */

// ============================================================================
// Market Conditions & Health
// ============================================================================

export interface ComponentScore {
  name: string
  score: number
  value: number | null
  interpretation: string
  signal: 'Bullish' | 'Neutral' | 'Bearish'
  lastUpdated?: string | null
}

export interface SectorScore {
  symbol: string
  name: string
  price: number | null
  changePct: number | null
  signal: 'Leading' | 'Neutral' | 'Lagging' | 'Unknown'
  lastUpdated?: string | null
}

export interface MarketHealthScore {
  overallScore: number
  overallLabel: string
  components: ComponentScore[]
  sectors: SectorScore[]
  lastUpdated: string
}

export interface MarketConditionsResponse {
  sp500: {
    price: number | null
    changePct: number | null
    lastUpdated?: string
  }
  vix: {
    price: number | null
    level: number | null
    lastUpdated?: string
  }
  tnx: {
    yield: number | null
    lastUpdated?: string
  }
  dxy: {
    price: number | null
    lastUpdated?: string
  }
  health: MarketHealthScore
}

export interface PriceResponse {
  symbol: string
  price: number
  beta: number | null
  volatility: number | null
  sector: string | null
}

export interface PricesResponse {
  prices: Record<string, PriceResponse>
  count: number
}

export interface FearGreedReading {
  date: string
  score: number
  label: 'Extreme Fear' | 'Fear' | 'Neutral' | 'Greed' | 'Extreme Greed'
  previousScore?: number
  scoreChange?: number
  signalCount: number
}

export interface FearGreedComponent {
  date: string
  vixPct?: number
  momentumPct?: number
  rsiPct?: number
  pcrPct?: number
  creditPct?: number
  windowDays: number
}

export interface FearGreedResponse {
  reading: FearGreedReading
  components?: FearGreedComponent
}

export interface MarketTrendsResponse {
  dates: string[]
  fearGreedScores: number[]
  marketHealthScores: number[]
}

// ============================================================================
// Market Intelligence (unified endpoint)
// ============================================================================

export interface PutCallContext {
  trend: 'up' | 'down' | 'flat'
  trendPct: number
  percentileRank: number
}

export interface EnrichedIndicator {
  value: number
  changePct: number | null
  label: string
  shortLabel: string
  tooltip: string
  signal: 'Bullish' | 'Neutral' | 'Bearish'
  emoji: string
  lastUpdated: string | null
  context?: PutCallContext
}

export interface SectorInfo {
  symbol: string
  name: string
  description: string
  price: number | null
  changePct: number | null
  signal: 'Leading' | 'Neutral' | 'Lagging'
  lastUpdated: string | null
}

export interface SectorRotationSummary {
  leading: SectorInfo[]
  neutral: SectorInfo[]
  lagging: SectorInfo[]
  leadingCount: number
  neutralCount: number
  laggingCount: number
}

export interface MarketHealthScoreSimple {
  overallScore: number
  overallLabel: string
  lastUpdated: string
  trend?: 'up' | 'down' | 'flat' | null
  trendChange?: number | null
}

export interface FearGreedScore {
  score: number
  label: 'Extreme Fear' | 'Fear' | 'Neutral' | 'Greed' | 'Extreme Greed'
  scoreChange: number | null
  signalCount: number
  lastUpdated: string
  isStale: boolean
  ageDays: number
  trend?: 'up' | 'down' | 'flat' | null
  trendChange?: number | null
}

export interface SectorWeight {
  sector: string
  weightPct: number
}

export interface OptionsActivityMetrics {
  nearTermPct: number
  nearTermSignal: 'High' | 'Normal' | 'Low'
  concentrationPct: number
  concentrationSignal: 'Focused' | 'Balanced' | 'Dispersed'
  topSectors: SectorWeight[]
  lastUpdated: string
}

export interface MarketIntelligenceResponse {
  narrative: string
  marketHealth: MarketHealthScoreSimple
  fearGreed: FearGreedScore
  indicators: Record<string, EnrichedIndicator>
  sectorRotation: SectorRotationSummary
  optionsActivity: OptionsActivityMetrics | null
  lastUpdated: string
}

// ============================================================================
// Market Prediction Committee
// ============================================================================

export type PredictionDirection = 'bullish' | 'neutral' | 'bearish'
export type PredictionTruthState =
  | 'live'
  | 'pendingTarget'
  | 'waitingAfterClose'
  | 'sparseHistory'
  | 'fetchError'
  | 'legacySparse'
  | 'pending_target'
  | 'waiting_after_close'
  | 'sparse_history'
  | 'fetch_error'
  | 'legacy_sparse'
export type PredictionSourceFreshness =
  | 'fresh'
  | 'stale'
  | 'missing'
  | 'unknown'
export type PredictionFreshnessState =
  | 'fresh'
  | 'aging'
  | 'stale'
  | 'invalid'
  | 'degraded'
export type CommitteeRosterMode =
  | 'defaultRoster'
  | 'customRoster'
  | 'default_roster'
  | 'custom_roster'
export type CommitteeExecutionPath =
  | 'committeeEndpoint'
  | 'fallbackCompletion'
  | 'committee_endpoint'
  | 'fallback_completion'

export interface PredictionSourceCluster {
  cluster: string
  weight?: number | null
  freshness?: PredictionSourceFreshness | null
  note?: string | null
}

export interface MarketPredictionCommitteeSummary {
  heroHeadline?: string | null
  overallBias?: string | null
  headline?: string | null
  marketRegimeSummary?: string | null
  confidenceNote?: string | null
  highestConvictionViews?: string[]
  highestConvictionCalls?: string[]
  heroDisagreementLabel?: string | null
  disagreementLabel?: string | null
  gapCallouts?: string[]
  scorecardStatusNote?: string | null
  committeeRosterMode?: CommitteeRosterMode | null
  committeeExecutionPath?: CommitteeExecutionPath | null
  executedSeatKeys?: string[]
  truthState?: PredictionTruthState | null
  [key: string]: unknown
}

export interface MacroCalendarSourceCluster {
  freshness?: PredictionSourceFreshness | null
  reason?:
    | 'ok'
    | 'staleTable'
    | 'noFutureRows'
    | 'stale_table'
    | 'no_future_rows'
    | null
  upcomingEventCount?: number | null
  nextEventDate?: string | null
  [key: string]: unknown
}

export interface MarketPredictionSourceSnapshotClusters {
  macroCalendar?: MacroCalendarSourceCluster | null
  [clusterName: string]: unknown
}

export interface MarketPredictionSourceSnapshot {
  clusters?: MarketPredictionSourceSnapshotClusters | null
  [key: string]: unknown
}

export interface MarketPredictionCall {
  id?: string | null
  symbol: string
  windowDays: number
  directionLabel: PredictionDirection
  probUp: number
  expectedMovePct: number
  confidenceBandLowPct?: number | null
  confidenceBandHighPct?: number | null
  confidenceScore?: number | null
  committeeDisagreementScore?: number | null
  rationaleSummary?: string | null
  topSourceClusters: PredictionSourceCluster[]
}

export interface CommitteeSeatVote {
  seatKey: string
  agentSlug: string
  modelId?: string | null
  provider?: string | null
  symbol: string
  windowDays: number
  directionLabel: PredictionDirection
  probUp: number
  expectedMovePct: number
  confidenceScore?: number | null
  rationaleSummary?: string | null
  sourceClusters: PredictionSourceCluster[]
}

export interface MarketPredictionScorecard {
  directionHitRate?: number | null
  moveMaePct?: number | null
  brierScore?: number | null
  sampleSize: number
}

export interface PredictionFreshnessCluster {
  cluster: string
  freshness: PredictionSourceFreshness
  asOfDate?: string | null
  detail?: string | null
}

export interface PredictionFreshnessSummary {
  state: PredictionFreshnessState
  summary: string
  invalidated: boolean
  generatedAgeSeconds: number
  evaluatedAgeSeconds?: number | null
  marketStatus: 'open' | 'pre_market' | 'after_hours' | 'closed' | string
  marketDate: string
  refreshAfterSeconds: number
  checkedAt: string
  reasonCodes: string[]
  criticalClusters: PredictionFreshnessCluster[]
}

export interface MarketPredictionCommitteeResponse {
  asOfTs: string
  generatedAt: string
  windowDays: number
  baseDate: string
  targetDate: string
  targetUniverse: string[]
  leadCall: MarketPredictionCall
  calls: MarketPredictionCall[]
  votes: CommitteeSeatVote[]
  scorecard?: MarketPredictionScorecard | null
  committeeSummary: MarketPredictionCommitteeSummary
  sourceSnapshot: MarketPredictionSourceSnapshot
  lastEvaluatedAt?: string | null
  freshnessSummary?: PredictionFreshnessSummary | null
}

export interface MarketPredictionReviewChangeItem {
  kind: 'seat'
  key: string
  priorWeight: number
  effectiveWeight: number
}

export interface MarketPredictionSeatScorecard {
  seatKey: string
  priorWeight: number
  effectiveWeight: number
  sampleSize: number
  directionHitRate?: number | null
  moveMaePct?: number | null
  brierScore?: number | null
  skillScore?: number | null
  recommendedAction: 'upweight' | 'downweight' | 'hold'
}

export interface MarketPredictionReviewSummary {
  generatedAt: string
  reviewState: 'live' | 'warmup' | 'degraded'
  driftCallouts: string[]
  topUpweighted: MarketPredictionReviewChangeItem[]
  topDownweighted: MarketPredictionReviewChangeItem[]
}

export interface MarketPredictionSeatReviewResponse {
  asOfTs: string
  windowDays: number
  reviewState: 'live' | 'warmup' | 'degraded'
  seatScorecards: MarketPredictionSeatScorecard[]
  reviewSummary: MarketPredictionReviewSummary
}

export interface MarketPredictionHistoryResponse {
  symbol: string
  windowDays: number
  items: MarketPredictionCall[]
}

// ============================================================================
// Historical Data
// ============================================================================

export interface FearGreedHistoryResponse {
  dates: string[]
  scores: number[]
  labels: string[]
  putCallRatios: (number | null)[]
}

export interface NewsSentimentHistoryResponse {
  dates: string[]
  scores: number[] // -1 to +1
  positiveCounts: number[]
  negativeCounts: number[]
  articleCounts: number[]
}

export interface IndicatorDataPoint {
  date: string
  close: number
  pctChange: number
}

export interface IndicatorHistoryResponse {
  sp500: IndicatorDataPoint[]
  vix: IndicatorDataPoint[]
  tnx: IndicatorDataPoint[]
  dxy: IndicatorDataPoint[]
  periodStart: string
  periodEnd: string
}

export interface SectorDataPoint {
  date: string
  close: number
  pctChange: number
}

export interface SectorHistory {
  name: string
  symbol: string
  data: SectorDataPoint[]
  currentPct: number
}

export interface SectorHistoryResponse {
  sectors: SectorHistory[]
  periodStart: string
  periodEnd: string
}

// ============================================================================
// Market Movers & Status
// ============================================================================

export interface MarketMoverItem {
  symbol: string
  name: string | null
  price: number
  changePct: number
  volume: number | null
  marketCap: number | null
  avgVolume: number | null
  rvol: number | null
  sector: string | null
}

export interface MarketMoversResponse {
  gainers: MarketMoverItem[]
  losers: MarketMoverItem[]
  mostActive: MarketMoverItem[]
  topRvol: MarketMoverItem[]
  source: string
  lastUpdated: string | null
}

export interface MarketStatusResponse {
  status: 'open' | 'closed' | 'pre_market' | 'after_hours'
  isOpen: boolean
  lastTradingDay: string
  nextTradingDay: string
  currentTimeEt: string
  expectedDataDate: string
  isHoliday: boolean
  holidayName: string | null
  isEarlyClose: boolean
  earlyCloseName: string | null
}

// ============================================================================
// Market Events
// ============================================================================

export interface MarketEvent {
  id: number
  date: string
  time: string | null
  type: string
  title: string
  label: string
  color: string
  impactScore: number | null
  actualValue: number | null
  expectedValue: number | null
  surprisePct: number | null
}

export interface MarketEventsChartResponse {
  events: MarketEvent[]
  total: number
  startDate: string
  endDate: string
}

export interface MarketEventType {
  eventType: string
  label: string
  shortLabel: string
  color: string
  frequency: string
  impact: string
}

export interface MarketEventTypesResponse {
  types: MarketEventType[]
}

/**
 * Shared TypeScript types for Market data API
 */

// ============================================================================
// Market Conditions & Health
// ============================================================================

export type MarketDataHorizon =
  | 'intraday'
  | 'latest_close'
  | 'one_day'
  | 'one_month'
  | 'prediction_window'

export const MARKET_DATA_HORIZON_LABELS: Record<MarketDataHorizon, string> = {
  intraday: 'Intraday/current',
  latest_close: 'Latest close',
  one_day: '1D',
  one_month: '1M',
  prediction_window: 'Prediction window',
}

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
// Historical Data
// ============================================================================

export interface FearGreedHistoryResponse {
  dates: string[]
  scores: number[]
  labels: string[]
  sources?: ('daily_close' | 'live_proxy')[]
  latestSource?: 'daily_close' | 'live_proxy'
  latestAsOf?: string | null
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

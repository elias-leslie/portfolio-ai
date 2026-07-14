import { get, post } from './client'

export interface SymbolPillarScore {
  score: number | null
  weight: number
  subScores?: Record<string, number | string | null> | null
  metadata?: Record<string, unknown> | null
  stale: boolean
}

export interface SymbolScoresSection {
  overall: number | null
  signalType: string | null
  signalStrength: number | null
  pillars: Record<string, SymbolPillarScore>
  dataQuality?: Record<string, unknown> | null
}

export interface SymbolSignalSection {
  type: string | null
  strength: number | null
  confirmations?: number | null
  reasons?: {
    bullish?: string[]
    bearish?: string[]
  } | null
  avoidFlags: number
}

export interface SymbolTradingSection {
  style: string | null
  confidence: number | null
  holdingPeriod: string | null
  riskLevel: string | null
  entryPrice: number | null
  stopLoss: number | null
  profitTarget: number | null
  positionSizeShares: number | null
  positionSizeDollars: number | null
}

export interface SymbolQuoteSection {
  price: number | null
  source?: string | null
  cachedAt?: string | null
  session?: string | null
  freshnessStatus: string
  freshnessLabel: string
  error?: string | null
}

export interface SymbolPortfolioSection {
  held: boolean
  position?: {
    shares: number
    costBasis: number
    currentValue: number | null
    gain: number | null
    gainPct: number | null
    weightPct: number | null
    concentrationWeightPct?: number | null
    concentrationMethod?: string | null
    topExposureName?: string | null
  } | null
  context?: {
    totalValue: number
    numHoldings: number
    diversificationScore?: number | null
    sectorWeight?: number | null
    concentrationTop3?: number | null
  } | null
}

export interface SymbolRecommendationSection {
  action: string
  reasoning: string[]
  ifNotHeld?: {
    action?: string
    sizePct?: number
    reasoning?: string
  } | null
}

export interface SymbolDecisionSection {
  action: string
  headline: string
  summary: string
  reasoning: string[]
  sourceKind: string
  sourceLabel: string
  sourceTimestamp?: string | null
  severity?: string | null
}

export interface SymbolNewsSection {
  sentimentScore?: number | null
  sentimentLabel?: string | null
  articleCount24H: number
  headline?: string | null
  keyEvents: Array<{
    icon: string
    text: string
    timeAgo: string
  }>
  recentArticles: Array<{
    headline: string
    url?: string | null
    source?: string | null
    publishedAt?: string | null
  }>
}

export interface SymbolMarketSection {
  fearGreedScore?: number | null
  fearGreedLabel?: string | null
  fearGreedAsOfDate?: string | null
  healthScore?: number | null
  vix?: number | null
  vixAsOfDate?: string | null
  sp500Change?: number | null
  sp500AsOfDate?: string | null
  sector?: {
    name?: string | null
    signal?: string | null
    dailyChange?: number | null
    relativeToSpy?: number | null
  } | null
}

export interface SymbolAlert {
  icon: string
  label: string
  tooltip?: string | null
  priority: number
  category?: string | null
}

export interface SymbolIntelligence {
  symbol: string
  generatedAt: string
  scores?: SymbolScoresSection | null
  signal?: SymbolSignalSection | null
  trading?: SymbolTradingSection | null
  quote?: SymbolQuoteSection | null
  portfolio?: SymbolPortfolioSection | null
  news?: SymbolNewsSection | null
  market?: SymbolMarketSection | null
  alerts: SymbolAlert[]
  recommendation?: SymbolRecommendationSection | null
  decision?: SymbolDecisionSection | null
  error?: string | null
}

export interface SymbolWorkflowEvent {
  id: string
  symbol: string
  fromStage?: string | null
  toStage: string
  note: string
  createdBy: string
  createdAt: string
  metadata?: Record<string, unknown>
}

export interface SymbolWorkflowPositionContext {
  shares: number
  costBasis: number
  marketValue: number | null
  gainPct: number | null
  weightPct: number | null
}

export interface SymbolWorkflowOutcomeSnapshot {
  action: string
  stage: string
  note: string
  createdAt: string
  jennyVerdict: string | null
  managementAction: string | null
  position: SymbolWorkflowPositionContext | null
}

export interface SymbolWorkflow {
  symbol: string
  stage: string
  summary: string
  lastTransitionAt: string
  updatedBy: string
  notes?: string | null
  nextReviewAt?: string | null
  availableTransitions: string[]
  position: SymbolWorkflowPositionContext | null
  latestOutcome: SymbolWorkflowOutcomeSnapshot | null
  history: SymbolWorkflowEvent[]
}

export async function fetchSymbolIntelligence(
  symbol: string,
  options?: { forceQuoteRefresh?: boolean },
): Promise<SymbolIntelligence> {
  const params = new URLSearchParams()
  if (options?.forceQuoteRefresh) {
    params.set('force_quote_refresh', 'true')
    params.set('_', String(Date.now()))
  }
  const query = params.toString()
  return get<SymbolIntelligence>(
    `/api/symbols/${symbol}/intelligence${query ? `?${query}` : ''}`,
  )
}

export async function fetchSymbolWorkflow(
  symbol: string,
): Promise<SymbolWorkflow> {
  return get<SymbolWorkflow>(`/api/symbols/${symbol}/workflow`)
}

export async function transitionSymbolWorkflow(
  symbol: string,
  payload: { stage: string; note?: string },
): Promise<SymbolWorkflow> {
  return post<SymbolWorkflow>(
    `/api/symbols/${symbol}/workflow/transition`,
    payload,
  )
}

export async function recordSymbolWorkflowOutcome(
  symbol: string,
  payload: {
    action: string
    note?: string
    jennyVerdict?: string | null
    managementAction?: string | null
  },
): Promise<SymbolWorkflow> {
  return post<SymbolWorkflow>(
    `/api/symbols/${symbol}/workflow/outcome`,
    payload,
  )
}

import { get } from './client'

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

export interface SymbolPortfolioSection {
  held: boolean
  position?: {
    shares: number
    costBasis: number
    currentValue: number
    gain: number
    gainPct: number
    weightPct: number
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
    source?: string | null
    publishedAt?: string | null
  }>
}

export interface SymbolMarketSection {
  fearGreedScore?: number | null
  fearGreedLabel?: string | null
  healthScore?: number | null
  vix?: number | null
  sp500Change?: number | null
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
  portfolio?: SymbolPortfolioSection | null
  news?: SymbolNewsSection | null
  market?: SymbolMarketSection | null
  alerts: SymbolAlert[]
  recommendation?: SymbolRecommendationSection | null
  error?: string | null
}

export async function fetchSymbolIntelligence(
  symbol: string,
): Promise<SymbolIntelligence> {
  return get<SymbolIntelligence>(`/api/symbols/${symbol}/intelligence`)
}

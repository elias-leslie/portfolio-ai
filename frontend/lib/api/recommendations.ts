/**
 * Recommendations API client functions
 */

import { apiRequest } from './client'

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface TradeRecommendation {
  symbol: string
  strategyId: string
  strategyName: string
  strategyType: string
  signalStrength: number
  signalType: 'BUY' | 'SELL' | 'HOLD'
  signalReasons: string[]
  entryPrice: number // Price when signal was generated
  currentPrice: number // Real-time current price
  priceChangePct: number // % change since signal
  signalStatus: 'valid' | 'better_entry' | 'caution' | 'invalidated'
  stopLoss: number
  targetPrice: number
  positionSizeDollars: number
  positionSizeShares: number
  riskRewardRatio: number
  expectedSharpe: number | null
  signalDate: string
  generatedAt: string | null
  validationType: 'thesis' | 'backtest' | 'both'
}

export interface RecommendationsSummary {
  buySignals: number
  sellSignals: number
  holdSignals: number
  totalPositionSize: number
  avgSignalStrength: number
  portfolioSize: number
  positionPct: number
}

export interface RecommendationsResponse {
  recommendations: TradeRecommendation[]
  total: number
  summary: RecommendationsSummary
}

export interface TrackPortfolioResponse {
  status: string
  position: {
    id: string
    symbol: string
    shares: number
    costBasis: number
    accountName: string
    strategyName: string
  }
  message: string
}

// ============================================================================
// API Functions
// ============================================================================

export async function getRecommendations(params?: {
  minStrength?: number
  limit?: number
  signalType?: 'BUY' | 'SELL' | 'all'
  portfolioSize?: number
  positionPct?: number
}): Promise<RecommendationsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.minStrength !== undefined)
    searchParams.set('min_strength', params.minStrength.toString())
  if (params?.limit) searchParams.set('limit', params.limit.toString())
  if (params?.signalType) searchParams.set('signal_type', params.signalType)
  if (params?.portfolioSize)
    searchParams.set('portfolio_size', params.portfolioSize.toString())
  if (params?.positionPct)
    searchParams.set('position_pct', params.positionPct.toString())

  const query = searchParams.toString()
  return apiRequest<RecommendationsResponse>(
    `/api/recommendations${query ? `?${query}` : ''}`,
  )
}

export async function trackInPortfolio(
  symbol: string,
  strategyId: string,
  accountId: string,
  shares: number,
): Promise<TrackPortfolioResponse> {
  const params = new URLSearchParams()
  params.set('strategy_id', strategyId)
  params.set('account_id', accountId)
  params.set('shares', shares.toString())

  return apiRequest<TrackPortfolioResponse>(
    `/api/recommendations/track/${symbol}?${params.toString()}`,
    { method: 'POST' },
  )
}

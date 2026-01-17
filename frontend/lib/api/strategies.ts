/**
 * Strategies API client functions
 */

import { apiRequest } from './client'

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface StrategyListItem {
  id: string
  name: string
  symbol: string
  strategyType: string
  status: 'testing' | 'active' | 'archived'
  version: number
  expectedSharpe: number | null
  liveSharpeRatio: number | null
  liveWinRate: number | null
  tradesCount: number
  createdAt: string
  activationDate: string | null
}

export interface StrategyDetail extends StrategyListItem {
  parameters: Record<string, unknown>
  researchSummary: ResearchSummary
  generationReasoning: string
  backtestMetrics: BacktestMetric[]
  expectedWinRate: number | null
  expectedMaxDrawdown: number | null
  liveTradesCount: number
  archiveDate: string | null
  archiveReason: string | null
  performanceHistory: PerformanceHistoryEntry[]
}

export interface ResearchSummary {
  symbol: string
  asOfDate: string
  newsSentimentTrend: string
  newsSentimentScore: number
  companyHealth: string
  fundamentalScore: number
  valuationTier: string
  trendStrength: string
  marketRegime: string
  fearGreedScore: number
  sector: string
  sectorMomentum: string
  overallConfidence: number
}

export interface BacktestMetric {
  windowStart: string
  windowEnd: string
  sharpe: number
  winRate: number
  maxDrawdown: number
  totalReturn: number
}

export interface PerformanceHistoryEntry {
  date: string
  trades30D: number
  winRate30D: number | null
  sharpeRatio30D: number | null
  maxDrawdown30D: number | null
  status: string
}

export interface StrategiesListResponse {
  strategies: StrategyListItem[]
  total: number
}

export interface GenerateStrategyRequest {
  symbol: string
  forceRegenerate?: boolean
}

export interface GenerateBatchRequest {
  symbols?: string[]
  topN?: number
  forceRegenerate?: boolean
}

export interface GenerateStrategyResponse {
  workflowId?: string
  status: string
  strategyId?: string
  commitSha?: string
  message?: string
  errorMessage?: string
}

export interface GenerateBatchResponse {
  status: string
  symbolsProcessed?: number
  strategiesGenerated?: number
  symbolsEvaluated?: number
  results?: Array<{
    symbol: string
    status: string
    strategyId: string | null
    message: string | null
  }>
  details?: string[]
}

export interface UpdateStrategyStatusRequest {
  status: 'active' | 'archived'
  archiveReason?: string
}

export interface StrategyPerformance {
  expected: {
    sharpe: number
    winRate: number | null
    maxDrawdown: number | null
  }
  actual30D: {
    sharpe: number
    winRate: number | null
    tradesCount: number
  }
  performanceRatio: number
  status:
    | 'no_live_data'
    | 'exceeding_expectations'
    | 'meeting_expectations'
    | 'underperforming'
}

// ============================================================================
// API Functions
// ============================================================================

export async function getStrategies(params?: {
  symbol?: string
  status?: 'testing' | 'active' | 'archived'
  strategy_type?: string
  limit?: number
}): Promise<StrategiesListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.symbol) searchParams.set('symbol', params.symbol)
  if (params?.status) searchParams.set('status', params.status)
  if (params?.strategy_type)
    searchParams.set('strategy_type', params.strategy_type)
  if (params?.limit) searchParams.set('limit', params.limit.toString())

  const query = searchParams.toString()
  return apiRequest<StrategiesListResponse>(
    `/api/strategies/${query ? `?${query}` : ''}`,
  )
}

export async function getStrategy(strategyId: string): Promise<StrategyDetail> {
  return apiRequest<StrategyDetail>(`/api/strategies/${strategyId}`)
}

export async function generateStrategy(
  request: GenerateStrategyRequest,
): Promise<GenerateStrategyResponse> {
  return apiRequest<GenerateStrategyResponse>('/api/strategies/generate', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function generateStrategiesBatch(
  request: GenerateBatchRequest,
): Promise<GenerateBatchResponse> {
  return apiRequest<GenerateBatchResponse>('/api/strategies/generate-batch', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function updateStrategyStatus(
  strategyId: string,
  request: UpdateStrategyStatusRequest,
): Promise<{ strategy: StrategyListItem; message: string }> {
  return apiRequest<{ strategy: StrategyListItem; message: string }>(
    `/api/strategies/${strategyId}`,
    {
      method: 'PATCH',
      body: JSON.stringify(request),
    },
  )
}

export async function getStrategyPerformance(
  strategyId: string,
): Promise<StrategyPerformance> {
  return apiRequest<StrategyPerformance>(
    `/api/strategies/${strategyId}/performance`,
  )
}

// ============================================================================
// Strategy Seeds API (FEAT-218)
// ============================================================================

export interface StrategySeed {
  id: string
  symbol: string
  thesis: string
  confidence: number
  status: 'pending' | 'processing' | 'converted' | 'rejected'
  strategyId: string | null
  createdAt: string
  processedAt: string | null
}

export interface StrategySeedsListResponse {
  seeds: StrategySeed[]
  total: number
}

export interface StrategyEvolution {
  strategyId: string
  name: string
  symbol: string
  status: string
  seed: {
    id: string
    thesis: string
    confidence: number
    createdAt: string
  } | null
  backtests: Array<{
    id: string
    startDate: string | null
    endDate: string | null
    sharpeRatio: number | null
    totalReturnPct: number | null
    maxDrawdownPct: number | null
    winRate: number | null
    numTrades: number
    status: string
    createdAt: string | null
  }>
  signals: Array<{
    id: string
    action: string
    strength: number | null
    confidenceScore: number | null
    entryPrice: number | null
    targetPrice: number | null
    createdAt: string | null
  }>
  trades: Array<{
    id: string
    symbol: string
    entryPrice: number | null
    exitPrice: number | null
    returnPct: number | null
    status: string
    createdAt: string | null
  }>
  performance: {
    expectedSharpe: number | null
    liveSharpe: number | null
    liveWinRate: number | null
    totalTrades: number
  }
}

export async function getStrategySeeds(params?: {
  status?: string
  symbol?: string
  limit?: number
  offset?: number
}): Promise<StrategySeedsListResponse> {
  const searchParams = new URLSearchParams()
  if (params?.status) searchParams.set('status', params.status)
  if (params?.symbol) searchParams.set('symbol', params.symbol)
  if (params?.limit) searchParams.set('limit', params.limit.toString())
  if (params?.offset) searchParams.set('offset', params.offset.toString())

  const query = searchParams.toString()
  return apiRequest<StrategySeedsListResponse>(
    `/api/strategy-seeds/${query ? `?${query}` : ''}`,
  )
}

export async function getStrategySeed(seedId: string): Promise<StrategySeed> {
  return apiRequest<StrategySeed>(`/api/strategy-seeds/${seedId}`)
}

export async function getStrategyEvolution(
  strategyId: string,
): Promise<StrategyEvolution> {
  return apiRequest<StrategyEvolution>(
    `/api/strategies/${strategyId}/evolution`,
  )
}

/**
 * Portfolio API client functions
 */

import { del, get, post, put } from './client'

// Types matching backend Pydantic models
export interface Account {
  id: string
  name: string
  accountType: string
  cashBalance: number
  createdAt: string
  updatedAt: string
}

export interface Position {
  id: string
  accountId: string
  symbol: string
  shares: number
  costBasis: number
  positionType: string
  createdAt: string
  updatedAt: string
}

export interface PositionWithValue extends Position {
  currentPrice: number
  currentValue: number
  gain: number
  gainPct: number
}

export interface PortfolioResponse {
  positions: PositionWithValue[]
  cashBalanceTotal: number
  totalValue: number
  totalCostBasis: number
  totalGain: number
  totalGainPct: number
}

export interface PositionPerformance {
  symbol: string
  gainPct: number
  gainAmount: number
  currentValue: number
  weightPct: number
}

export interface RiskProfile {
  level: string
  score: number
  factors: Record<string, string>
}

export interface DiversificationScore {
  score: number
  level: string
  numHoldings: number
  numSectors: number
}

export interface PortfolioAnalytics {
  portfolioValue: {
    totalValue: number
    totalCostBasis: number
    totalGain: number
    totalGainPct: number
  }
  portfolioBeta: number
  portfolioVolatility: number
  sharpeRatio: number | null
  concentration: {
    topHoldingPct: number
    top3Pct: number
    top10Pct: number
    herfindahlIndex: number
  }
  sectorExposure: Record<string, number>
  riskProfile: RiskProfile | null
  diversificationScore: DiversificationScore | null
  topPerformers: PositionPerformance[]
  bottomPerformers: PositionPerformance[]
  numPositions: number
  numSymbols: number
}

export interface JennyRoutine {
  id: string
  routineType: string
  status: string
  triggeredBy: string
  summary: string | null
  agentsUsed: string[]
  symbolsScanned: number
  notificationsCreated: number
  startedAt: string
  completedAt: string | null
  metadata: Record<string, unknown>
}

export interface JennyEvaluation {
  id: string
  routineId: string
  symbol: string
  agentName: string
  provider: string | null
  model: string | null
  verdict: string
  confidence: number | null
  rationale: string
  recommendation: string | null
  strengths: string[]
  weaknesses: string[]
  thesisId: string | null
  agentRunId: string | null
  createdAt: string
  metadata: Record<string, unknown>
}

export interface JennySymbolReview {
  symbol: string
  finalVerdict: string
  averageConfidence: number | null
  thesisStatus: string | null
  thesisAction: string | null
  managementAction: string | null
  managementDetail: string | null
  positionGainPct: number | null
  positionWeightPct: number | null
  reasons: string[]
  evaluations: JennyEvaluation[]
}

export interface JennyNotification {
  id: string
  routineId: string | null
  symbol: string | null
  category: string
  severity: string
  status: string
  title: string
  detail: string
  recommendation: string | null
  createdAt: string
  acknowledgedAt: string | null
  metadata: Record<string, unknown>
}

export interface JennyTradeReview {
  id: string
  symbol: string
  thesisId: string | null
  ideaId: string | null
  reviewSource: string
  outcomeLabel: string
  returnPct: number | null
  lesson: string
  whatWorked: string | null
  whatFailed: string | null
  nextTime: string | null
  createdAt: string
  updatedAt: string
  agentConsensus: Record<string, unknown>
  metadata: Record<string, unknown>
}

export interface JennyAgentScorecard {
  agentName: string
  totalEvaluations: number
  completedReviews: number
  positiveVerdicts: number
  winRate: number | null
  avgReturnPct: number | null
  agreementRate: number | null
  calibrationScore: number | null
  entryQualityScore: number | null
  riskJudgmentScore: number | null
  exitTimingScore: number | null
  alertDisciplineScore: number | null
  strengths: string[]
  weaknesses: string[]
  lastEvaluationAt: string | null
  updatedAt: string
}

export interface JennyDashboard {
  routines: JennyRoutine[]
  notifications: JennyNotification[]
  symbolReviews: JennySymbolReview[]
  tradeReviews: JennyTradeReview[]
  scorecards: JennyAgentScorecard[]
}

export interface JennyRunResponse {
  routine: JennyRoutine
  dashboard: JennyDashboard
}

export interface CreateAccountRequest {
  name: string
  accountType: string
}

export interface AddPositionRequest {
  accountId: string
  symbol: string
  shares: number
  costBasis: number
  positionType: string
}

/**
 * Fetch all portfolio positions with current values
 */
export async function fetchPortfolio(): Promise<PortfolioResponse> {
  return get<PortfolioResponse>('/api/portfolio')
}

/**
 * Fetch all accounts
 */
export async function fetchAccounts(): Promise<Account[]> {
  return get<Account[]>('/api/portfolio/accounts')
}

/**
 * Create a new account
 */
export async function createAccount(
  data: CreateAccountRequest,
): Promise<Account> {
  return post<Account>('/api/portfolio/account', data)
}

/**
 * Delete an account by ID
 */
export async function deleteAccount(accountId: string): Promise<void> {
  await del<void>(`/api/portfolio/account/${accountId}`)
}

/**
 * Add or update a position
 */
export async function addPosition(data: AddPositionRequest): Promise<Position> {
  return post<Position>('/api/portfolio/position', data)
}

/**
 * Update an existing position
 */
export async function updatePosition(
  positionId: string,
  data: AddPositionRequest,
): Promise<Position> {
  return put<Position>(`/api/portfolio/position/${positionId}`, data)
}

/**
 * Delete a position by ID
 */
export async function deletePosition(positionId: string): Promise<void> {
  await del<void>(`/api/portfolio/position/${positionId}`)
}

/**
 * Fetch portfolio analytics (beta, volatility, concentration, sector exposure)
 */
export async function fetchAnalytics(): Promise<PortfolioAnalytics> {
  return get<PortfolioAnalytics>('/api/portfolio/analytics')
}

export async function fetchJennyDashboard(): Promise<JennyDashboard> {
  return get<JennyDashboard>('/api/portfolio/jenny')
}

export async function runJennyRoutine(
  routineType: 'dailyOperator' | 'weeklyLearning',
): Promise<JennyRunResponse> {
  return post<JennyRunResponse>('/api/portfolio/jenny/run', { routineType })
}

export async function acknowledgeJennyNotification(
  notificationId: string,
): Promise<JennyNotification> {
  return post<JennyNotification>(
    `/api/portfolio/jenny/notifications/${notificationId}/acknowledge`,
  )
}

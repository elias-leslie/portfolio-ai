/**
 * Watchlist API client functions
 */

import { apiRequest } from './client'
import type { SymbolDecisionSection, SymbolQuoteSection } from './symbols'

// Types matching backend Pydantic models
export interface ScoreComponent {
  score: number
  weight: number
  stale: boolean
  updatedAt?: string
  metadata?: Record<string, unknown>
  subScores?: Record<string, number> // NEW: Sub-metric scores
}

export interface ScoreBreakdown {
  price: ScoreComponent
  technical: ScoreComponent
  fundamental?: ScoreComponent | null
  catalyst?: ScoreComponent | null
  optionsFlow?: ScoreComponent | null
  performanceFactor?: ScoreComponent | null
  overall: number
}

export interface SentimentProbabilities {
  [label: string]: number
}

export interface NewsSentimentDetail {
  score: number | null
  scoreChange: number | null
  positiveCount: number
  neutralCount: number
  negativeCount: number
  articleCount: number
  latestPublishedAt?: string | null
  topPositive?: SentimentArticle | null
  topNegative?: SentimentArticle | null
  modelBreakdown: Record<string, number>
}

export interface SentimentScoreMeta {
  score: number
  label: 'positive' | 'neutral' | 'negative'
  confidence: number
  model: string
  probabilities?: SentimentProbabilities
}

export interface SentimentArticle {
  symbol: string
  headline: string
  articleHash?: string | null
  url?: string | null
  summary?: string | null
  source?: string | null
  vendor?: string | null
  author?: string | null
  imageUrl?: string | null
  publishedAt?: string | null
  fetchedAt: string
  sentiment: SentimentScoreMeta
  contentHash: string
  raw?: Record<string, unknown>
  filingType?: string | null
  isMaterialEvent?: boolean
  // AI-generated insights
  impactSummary?: string | null
  actionableInsight?: string | null
  // ML quality prediction
  qualityPrediction?: boolean | null
  qualityConfidence?: number | null
  // Story clustering metadata
  storyId?: string | null
  isPrimaryArticle?: boolean
  coverageCount?: number
  // Structured decision support
  eventCategory?: string | null
  marketContextTopic?: string | null
  sourceSignalTier?: string | null
  canonicalHeadline?: string | null
  decisionValueScore?: number | null
  decisionValueLabel?: 'high' | 'medium' | 'low' | null
  decisionValueReason?: string | null
}

export interface RecentNewsPayload {
  summary?: NewsSentimentDetail
  articles: SentimentArticle[]
}

export interface KeyEvent {
  icon: string
  text: string
  timeAgo: string
  isMaterial: boolean
  eventCategory?: string | null
  publishedAt?: string | null
}

export interface NewsIntelligence {
  headline: string
  sentimentScore: number
  sentimentLabel: string
  articleCount24H: number
  keyEvents: KeyEvent[]
  recentArticles: Record<string, unknown>[]
}

export interface PriorityIndicator {
  icon: string
  label: string
  tooltip: string
  priority: number
  category: 'time_sensitive' | 'risk' | 'opportunity' | 'caution'
}

export interface PillarDataQuality {
  status: 'complete' | 'partial' | 'stale' | 'n/a'
  score: number
  details: string
}

export interface DataQuality {
  overallPct: number
  pillars: {
    [key: string]: PillarDataQuality
  }
}

export interface PriceTrend {
  key: 'D' | 'W' | 'M' | 'Q' | string
  label: string
  returnPct: number | null
  startClose: number | null
  endClose: number | null
  startDate: string | null
  endDate: string | null
  endSource: string
  status: string
}

export interface VwapSignal {
  status: string
  vwap: number | null
  price: number | null
  close: number | null
  distancePct: number | null
  asOfDate: string | null
  closeAsOfDate: string | null
  priceAsOf: string | null
  priceSource: string
  source: string
}

export interface WatchlistItem {
  id: string
  symbol: string
  companyName?: string | null
  note?: string
  source?: 'manual' | 'portfolio'
  createdAt: string
  updatedAt: string
  currentScore?: ScoreBreakdown
  quote?: SymbolQuoteSection | null
  priceTrends?: PriceTrend[]
  vwapSignal?: VwapSignal | null
  scoreAlert?: boolean
  // Narrative Intelligence fields
  signalType?: 'BUY' | 'HOLD' | 'AVOID' | null
  signalStrength?: number | null
  narrativeHeadline?: string | null
  recommendedStyle?: 'Index' | 'Trend' | 'Value' | 'Swing' | 'Event' | null
  styleConfidence?: number | null
  optimalHoldingPeriod?: string | null
  riskLevel?: 'Low' | 'Medium-Low' | 'Medium' | 'High' | null
  // Trade Calculator fields
  entryPrice?: number | null
  stopLoss?: number | null
  profitTarget?: number | null
  positionSizeShares?: number | null
  // News sentiment
  newsSentimentScore?: number | null
  recentNews?: RecentNewsPayload | null
  // News Intelligence
  newsIntelligence?: NewsIntelligence | null
  // Priority indicators
  priorityIndicators?: PriorityIndicator[]
  // Data Quality
  dataQuality?: DataQuality | null
  decision?: SymbolDecisionSection | null
}

export interface WatchlistListResponse {
  items: WatchlistItem[]
  totalCount: number
}

export interface WatchlistItemCreate {
  symbol: string
  note?: string
}

export interface WatchlistItemUpdate {
  note?: string
}

export interface FailedSymbolInfo {
  symbol: string
  reason: string
}

export interface RefreshResponse {
  status: string
  message: string
  refreshedCount: number
  failedCount?: number
  failed?: FailedSymbolInfo[]
}

export interface ScoreHistory {
  timestamp: string
  overall: number
  priceScore: number
  technicalScore: number
  price?: number | null
}

export interface ScoreHistoryResponse {
  itemId: string
  symbol: string
  history: ScoreHistory[]
}

export interface RefreshStatus {
  isRefreshing: boolean
  startedAt?: string
  elapsedSeconds?: number
  totalItems?: number
  processedItems?: number
  currentSymbol?: string
  percentComplete?: number
}

/**
 * Get all watchlist items
 *
 * Watchlist is user-level (not account-specific).
 */
export async function fetchWatchlistItems(): Promise<WatchlistListResponse> {
  return apiRequest<WatchlistListResponse>('/api/watchlist')
}

/**
 * Get a single watchlist item with details
 */
export async function fetchWatchlistItem(
  itemId: string,
): Promise<WatchlistItem> {
  return apiRequest<WatchlistItem>(`/api/watchlist/${itemId}`)
}

/**
 * Add a symbol to the watchlist
 */
export async function createWatchlistItem(
  data: WatchlistItemCreate,
): Promise<WatchlistItem> {
  return apiRequest<WatchlistItem>('/api/watchlist', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Update a watchlist item (notes)
 */
export async function updateWatchlistItem(
  itemId: string,
  data: WatchlistItemUpdate,
): Promise<WatchlistItem> {
  return apiRequest<WatchlistItem>(`/api/watchlist/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

/**
 * Delete a watchlist item
 */
export async function deleteWatchlistItem(itemId: string): Promise<void> {
  await apiRequest<void>(`/api/watchlist/${itemId}`, {
    method: 'DELETE',
  })
}

/**
 * Get refresh status for the watchlist
 */
export async function fetchRefreshStatus(): Promise<RefreshStatus> {
  return apiRequest<RefreshStatus>('/api/watchlist/refresh-status')
}

/**
 * Manually refresh watchlist scores
 */
export async function refreshWatchlistScores(): Promise<RefreshResponse> {
  return apiRequest<RefreshResponse>('/api/watchlist/refresh', {
    method: 'POST',
    body: JSON.stringify({}),
  })
}

/**
 * Get 7-day score history for a watchlist item
 */
export async function fetchScoreHistory(
  itemId: string,
): Promise<ScoreHistoryResponse> {
  return apiRequest<ScoreHistoryResponse>(`/api/watchlist/${itemId}/history`)
}

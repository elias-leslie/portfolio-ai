import { apiRequest } from './client'
import type { NewsSentimentDetail, SentimentArticle } from './watchlist'

export interface NewsBundle {
  symbol: string
  summary: NewsSentimentDetail
  articles: SentimentArticle[]
}

export type MarketNewsResponse = NewsBundle

export interface WatchlistNewsResponse {
  accountId: string
  items: NewsBundle[]
  status?: 'hidden' | 'ok'
}

export interface NewsHealthResponse {
  finbertAvailable: boolean
  marketLastRefreshedAt: string | null
  watchlistLastRefreshedAt: string | null
  fallbackHeadlines24H: number
  headlines24H: number
  cacheTtlHours: number
  lookbackWindowHours: number
  fallbackRate24H: number
  fallbackAvgLatencyMs24H: number | null
  fallbackP95LatencyMs24H: number | null
  fallbackLastEventAt: string | null
  vendors: Record<string, VendorHealth>
}

export interface VendorHealth {
  configured: boolean
  enabled: boolean
  active: boolean
  lastAttemptAt: string | null
  lastSuccessAt: string | null
  lastErrorAt: string | null
  lastError: string | null
  articlesLastFetch: number
  articlesLast24H: number
  lastArticleAt: string | null
  notes: string | null
  reason: string | null
}

export interface SourceMetrics {
  vendor: string
  duplicateRate: number
  diversityScore: number
  confidenceAvg: number
  freshnessScore: number
  userUsefulRate: number | null
  qualityScore: number
  articleCount: number
  samplePeriodStart: string
  calculatedAt: string
}

type QueryParams = Record<string, string | number | boolean | undefined>

function buildQuery(params: QueryParams): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value))
    }
  })
  const queryString = searchParams.toString()
  return queryString ? `?${queryString}` : ''
}

export async function fetchNewsIntelligence(
  symbol?: string,
  options?: {
    limit?: number
    forceRefresh?: boolean
  },
): Promise<NewsBundle> {
  const query = buildQuery({
    symbol,
    limit: options?.limit,
    force_refresh: options?.forceRefresh,
  })
  return apiRequest<NewsBundle>(`/api/news${query}`)
}

export async function fetchWatchlistNews(
  accountId: string,
  options?: {
    maxResults?: number
    forceRefresh?: boolean
  },
): Promise<WatchlistNewsResponse> {
  const query = buildQuery({
    account_id: accountId,
    max_results: options?.maxResults,
    force_refresh: options?.forceRefresh,
  })
  return apiRequest<WatchlistNewsResponse>(`/api/news/watchlist${query}`)
}

export async function searchNews(
  query: string,
  options?: { maxResults?: number },
): Promise<NewsBundle> {
  const qs = buildQuery({
    query,
    max_results: options?.maxResults,
  })
  return apiRequest<NewsBundle>(`/api/news/search${qs}`)
}

export async function fetchNewsHealth(): Promise<NewsHealthResponse> {
  return apiRequest<NewsHealthResponse>('/api/news/health')
}

export async function fetchSourceMetrics(): Promise<SourceMetrics[]> {
  return apiRequest<SourceMetrics[]>('/api/news/source-stats')
}

export async function triggerNewsSourceProfiling(): Promise<{
  taskId?: string
  status?: string
  message?: string
}> {
  return apiRequest('/api/news/profile-sources', {
    method: 'POST',
  })
}

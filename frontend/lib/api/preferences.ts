/**
 * User preferences API client functions
 */

import { apiRequest } from './client'

// Weight configuration types (migration 019)
export interface ScoreWeights {
  price: number
  technical: number
  fundamental: number
}

export interface PriceSubWeights {
  changePct: number
}

export interface TechnicalSubWeights {
  rsi14: number
  trend: number
  macd: number
}

export interface FundamentalSubWeights {
  valuation: number
  growth: number
  health: number
  sentiment: number
}

// Types matching backend Pydantic models
export interface PreferencesResponse {
  riskTolerance: number
  allowLong: boolean
  allowShort: boolean
  allowOptions: boolean
  allowCrypto: boolean
  allowFutures: boolean
  maxPositionSizePct: number
  // Refresh control fields
  defaultRefreshMinutes: number
  watchlistRefreshOverride: number | null
  portfolioRefreshOverride: number | null
  newsRefreshOverride: number | null
  newsLookbackHours: number
  newsMaxArticles: number
  frontendPollInterval: number
  // Legacy watchlist fields (kept for backward compatibility)
  watchlistRefreshMinutes: number
  watchlistAutoExpand: boolean
  watchlistPriceWeight: number
  watchlistTechnicalWeight: number
  displayTimezone: string
  watchlistShowNews: boolean
  // New weight configuration fields (migration 019)
  watchlistScoreWeights?: ScoreWeights
  priceSubWeights?: PriceSubWeights
  technicalSubWeights?: TechnicalSubWeights
  fundamentalSubWeights?: FundamentalSubWeights
}

export interface PreferencesUpdate {
  riskTolerance?: number
  allowLong?: boolean
  allowShort?: boolean
  allowOptions?: boolean
  allowCrypto?: boolean
  allowFutures?: boolean
  maxPositionSizePct?: number
  // Refresh control fields
  defaultRefreshMinutes?: number
  watchlistRefreshOverride?: number | null
  portfolioRefreshOverride?: number | null
  newsRefreshOverride?: number | null
  newsLookbackHours?: number | null
  newsMaxArticles?: number | null
  frontendPollInterval?: number
  // Legacy watchlist fields (kept for backward compatibility)
  watchlistRefreshMinutes?: number
  watchlistAutoExpand?: boolean
  watchlistPriceWeight?: number
  watchlistTechnicalWeight?: number
  displayTimezone?: string
  watchlistShowNews?: boolean
  // New weight configuration fields (migration 019)
  watchlistScoreWeights?: ScoreWeights
  priceSubWeights?: PriceSubWeights
  technicalSubWeights?: TechnicalSubWeights
  fundamentalSubWeights?: FundamentalSubWeights
}

/**
 * Get user's risk tolerance and trade preferences
 */
export async function fetchPreferences(): Promise<PreferencesResponse> {
  return apiRequest<PreferencesResponse>('/api/preferences/')
}

/**
 * Update user preferences
 */
export async function updatePreferences(
  data: PreferencesUpdate,
): Promise<PreferencesResponse> {
  return apiRequest<PreferencesResponse>('/api/preferences/', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * User preferences API client functions
 */

import { get, post, put } from './client'

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
  thesisGenerationEnabled: boolean
  autoRemoveOnInvalidation: boolean
  autoTrimEnabled: boolean
  scheduledJennyOperatorEnabled: boolean
  scheduledMlLabelingEnabled: boolean
  scheduledStrategyResearchEnabled: boolean
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
  thesisGenerationEnabled?: boolean
  autoRemoveOnInvalidation?: boolean
  autoTrimEnabled?: boolean
  scheduledJennyOperatorEnabled?: boolean
  scheduledMlLabelingEnabled?: boolean
  scheduledStrategyResearchEnabled?: boolean
  // New weight configuration fields (migration 019)
  watchlistScoreWeights?: ScoreWeights
  priceSubWeights?: PriceSubWeights
  technicalSubWeights?: TechnicalSubWeights
  fundamentalSubWeights?: FundamentalSubWeights
}

const DEFAULT_WATCHLIST_REFRESH_MINUTES = 15

export type RefreshPreferenceSnapshot = Pick<
  PreferencesResponse,
  | 'defaultRefreshMinutes'
  | 'watchlistRefreshOverride'
  | 'watchlistRefreshMinutes'
>

export function getWatchlistRefreshMinutes(
  preferences?: RefreshPreferenceSnapshot | null,
): number {
  if (!preferences) {
    return DEFAULT_WATCHLIST_REFRESH_MINUTES
  }

  if (
    typeof preferences.watchlistRefreshOverride === 'number' &&
    preferences.watchlistRefreshOverride > 0
  ) {
    return Math.max(
      preferences.watchlistRefreshOverride,
      DEFAULT_WATCHLIST_REFRESH_MINUTES,
    )
  }

  if (
    typeof preferences.defaultRefreshMinutes === 'number' &&
    preferences.defaultRefreshMinutes > 0
  ) {
    return Math.max(
      preferences.defaultRefreshMinutes,
      DEFAULT_WATCHLIST_REFRESH_MINUTES,
    )
  }

  return Math.max(
    preferences.watchlistRefreshMinutes || DEFAULT_WATCHLIST_REFRESH_MINUTES,
    DEFAULT_WATCHLIST_REFRESH_MINUTES,
  )
}

/**
 * Get user's risk tolerance and trade preferences
 */
export async function fetchPreferences(): Promise<PreferencesResponse> {
  return get<PreferencesResponse>('/api/preferences')
}

/**
 * Update user preferences
 */
export async function updatePreferences(
  data: PreferencesUpdate,
): Promise<PreferencesResponse> {
  return post<PreferencesResponse>('/api/preferences', data)
}

// L3 committee fan-out controls (master toggle + four numeric knobs).
export interface ScannerFanoutSettings {
  enabled: boolean
  topN: number
  tier1Keep: number
  maxDaily: number
  cacheTtlHours: number
}

export async function fetchScannerFanoutSettings(): Promise<ScannerFanoutSettings> {
  return get<ScannerFanoutSettings>('/api/preferences/scanner-fanout')
}

export async function updateScannerFanoutSettings(
  settings: ScannerFanoutSettings,
): Promise<ScannerFanoutSettings> {
  return put<ScannerFanoutSettings>('/api/preferences/scanner-fanout', settings)
}

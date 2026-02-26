/**
 * Market historical data API functions for trend charts
 */

import { apiRequest } from './client'
import type {
  FearGreedHistoryResponse,
  IndicatorHistoryResponse,
  NewsSentimentHistoryResponse,
  SectorHistoryResponse,
} from './market-types'

/**
 * Get Fear & Greed historical data for trend charts
 */
export async function fetchFearGreedHistory(
  days: number = 365,
): Promise<FearGreedHistoryResponse> {
  return apiRequest<FearGreedHistoryResponse>(
    `/api/market/fear-greed-history?days=${days}`,
  )
}

/**
 * Get news sentiment historical data for trend charts
 * @param days - Number of days of history
 * @param granularity - 'daily' or 'hourly'
 */
export async function fetchNewsSentimentHistory(
  days: number = 30,
  granularity: 'daily' | 'hourly' = 'daily',
): Promise<NewsSentimentHistoryResponse> {
  return apiRequest<NewsSentimentHistoryResponse>(
    `/api/market/news-sentiment-history?days=${days}&granularity=${granularity}`,
  )
}

/**
 * Get key indicator historical data for trend charts
 */
export async function fetchIndicatorHistory(
  days: number = 365,
): Promise<IndicatorHistoryResponse> {
  return apiRequest<IndicatorHistoryResponse>(
    `/api/market/indicator-history?days=${days}`,
  )
}

/**
 * Get sector ETF historical data for performance charts
 */
export async function fetchSectorHistory(
  days: number = 365,
): Promise<SectorHistoryResponse> {
  return apiRequest<SectorHistoryResponse>(
    `/api/market/sector-history?days=${days}`,
  )
}

/**
 * Core market data API functions: conditions, intelligence, prices, trends
 */

import { apiRequest } from './client'
import type {
  MarketConditionsResponse,
  MarketIntelligenceResponse,
  MarketTrendsResponse,
  PricesResponse,
} from './market-types'

/**
 * Get current market conditions (S&P 500, VIX, 10Y yield, USD index)
 */
export async function fetchMarketConditions(): Promise<MarketConditionsResponse> {
  return apiRequest<MarketConditionsResponse>('/api/market/conditions')
}

/**
 * Get unified market intelligence (narrative + dual scoring + sectors)
 */
export async function fetchMarketIntelligence(): Promise<MarketIntelligenceResponse> {
  return apiRequest<MarketIntelligenceResponse>('/api/market/intelligence')
}

/**
 * Get current prices for stock symbols
 */
export async function fetchPrices(symbols: string[]): Promise<PricesResponse> {
  const symbolsParam = symbols.join(',')
  return apiRequest<PricesResponse>(
    `/api/market/prices?symbols=${encodeURIComponent(symbolsParam)}`,
  )
}

/**
 * Get market trends for sparkline charts
 */
export async function fetchMarketTrends(
  days: number = 30,
): Promise<MarketTrendsResponse> {
  return apiRequest<MarketTrendsResponse>(`/api/market/trends?days=${days}`)
}

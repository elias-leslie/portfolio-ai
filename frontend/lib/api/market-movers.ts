/**
 * Market movers and market status API functions
 */

import { apiRequest } from './client'
import type { MarketMoversResponse, MarketStatusResponse } from './market-types'

/**
 * Get top market movers (gainers and losers)
 */
export async function fetchMarketMovers(
  count: number = 10,
  options: RequestInit = {},
): Promise<MarketMoversResponse> {
  return apiRequest<MarketMoversResponse>(
    `/api/market/movers?count=${count}`,
    options,
  )
}

/**
 * Get current market status including expected data date for staleness detection
 */
export async function fetchMarketStatus(
  options: RequestInit = {},
): Promise<MarketStatusResponse> {
  return apiRequest<MarketStatusResponse>('/api/market/status', options)
}

/**
 * Market events API functions (FOMC, CPI, NFP, etc.)
 */

import { apiRequest } from './client'
import type {
  MarketEventsChartResponse,
  MarketEventsResponse,
  MarketEventTypesResponse,
} from './market-types'

/**
 * Fetch market events for a date window (past and/or future)
 */
export async function fetchMarketEvents(
  startDate: string,
  endDate: string,
): Promise<MarketEventsResponse> {
  return apiRequest<MarketEventsResponse>(
    `/api/market/events?start_date=${startDate}&end_date=${endDate}`,
  )
}

/**
 * Fetch market events formatted for chart overlays
 */
export async function fetchMarketEventsForChart(
  days: number = 365,
  options: RequestInit = {},
): Promise<MarketEventsChartResponse> {
  return apiRequest<MarketEventsChartResponse>(
    `/api/market/events/chart?days=${days}`,
    options,
  )
}

/**
 * Fetch market event type metadata
 */
export async function fetchMarketEventTypes(): Promise<MarketEventTypesResponse> {
  return apiRequest<MarketEventTypesResponse>('/api/market/events/types')
}

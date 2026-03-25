import { get } from './client'

export interface TradingRulesResponse {
  watchlistManagement: {
    maxWatchlistSize: number
  }
}

export async function fetchTradingRules(): Promise<TradingRulesResponse> {
  return get<TradingRulesResponse>('/api/rules')
}

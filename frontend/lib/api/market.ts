/**
 * Market data API — barrel re-export for backwards compatibility.
 *
 * Sub-modules:
 *   market-types.ts   — all TypeScript interfaces
 *   market-core.ts    — conditions, intelligence, prices, fear-greed, trends
 *   market-history.ts — historical data for trend charts
 *   market-movers.ts  — market movers and market status
 *   market-events.ts  — economic calendar events (FOMC, CPI, NFP, …)
 */

export {
  fetchMarketConditions,
  fetchMarketIntelligence,
  fetchMarketPredictionCommittee,
  fetchMarketPredictionHistory,
  fetchMarketTrends,
  fetchPrices,
} from './market-core'
export {
  fetchMarketEventsForChart,
  fetchMarketEventTypes,
} from './market-events'

export {
  fetchFearGreedHistory,
  fetchIndicatorHistory,
  fetchNewsSentimentHistory,
  fetchSectorHistory,
} from './market-history'

export { fetchMarketMovers, fetchMarketStatus } from './market-movers'
export type {
  ComponentScore,
  EnrichedIndicator,
  FearGreedComponent,
  FearGreedHistoryResponse,
  FearGreedReading,
  FearGreedScore,
  IndicatorDataPoint,
  IndicatorHistoryResponse,
  MarketConditionsResponse,
  MarketEvent,
  MarketEventsChartResponse,
  MarketEventType,
  MarketEventTypesResponse,
  MarketHealthScore,
  MarketHealthScoreSimple,
  MarketIntelligenceResponse,
  MarketMoverItem,
  MarketMoversResponse,
  MarketPredictionCall,
  MarketPredictionCommitteeResponse,
  MarketPredictionHistoryResponse,
  MarketPredictionScorecard,
  MarketStatusResponse,
  MarketTrendsResponse,
  NewsSentimentHistoryResponse,
  OptionsActivityMetrics,
  PriceResponse,
  PricesResponse,
  PutCallContext,
  SectorDataPoint,
  SectorHistory,
  SectorHistoryResponse,
  SectorInfo,
  SectorRotationSummary,
  SectorScore,
  SectorWeight,
} from './market-types'

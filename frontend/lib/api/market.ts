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

export type {
  ComponentScore,
  SectorScore,
  MarketHealthScore,
  MarketConditionsResponse,
  PriceResponse,
  PricesResponse,
  FearGreedReading,
  FearGreedComponent,
  FearGreedResponse,
  MarketTrendsResponse,
  PutCallContext,
  EnrichedIndicator,
  SectorInfo,
  SectorRotationSummary,
  MarketHealthScoreSimple,
  FearGreedScore,
  SectorWeight,
  OptionsActivityMetrics,
  MarketIntelligenceResponse,
  FearGreedHistoryResponse,
  NewsSentimentHistoryResponse,
  IndicatorDataPoint,
  IndicatorHistoryResponse,
  SectorDataPoint,
  SectorHistory,
  SectorHistoryResponse,
  MarketMoverItem,
  MarketMoversResponse,
  MarketStatusResponse,
  MarketEvent,
  MarketEventsChartResponse,
  MarketEventType,
  MarketEventTypesResponse,
} from './market-types'

export {
  fetchMarketConditions,
  fetchMarketIntelligence,
  fetchPrices,
  fetchFearGreed,
  fetchMarketTrends,
} from './market-core'

export {
  fetchFearGreedHistory,
  fetchNewsSentimentHistory,
  fetchIndicatorHistory,
  fetchSectorHistory,
} from './market-history'

export { fetchMarketMovers, fetchMarketStatus } from './market-movers'

export { fetchMarketEventsForChart, fetchMarketEventTypes } from './market-events'

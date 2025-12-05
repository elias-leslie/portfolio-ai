/**
 * Market data API client functions
 */

import { apiRequest } from "./client";

// Types matching backend Pydantic models
export interface ComponentScore {
  name: string;
  score: number;
  value: number | null;
  interpretation: string;
  signal: "Bullish" | "Neutral" | "Bearish";
  last_updated?: string | null;
}

export interface SectorScore {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  signal: "Leading" | "Neutral" | "Lagging" | "Unknown";
  last_updated?: string | null;
}

export interface MarketHealthScore {
  overall_score: number;
  overall_label: string;
  components: ComponentScore[];
  sectors: SectorScore[];
  last_updated: string;
}

export interface MarketConditionsResponse {
  sp500: {
    price: number | null;
    change_pct: number | null;
    last_updated?: string;
  };
  vix: {
    price: number | null;
    level: number | null;
    last_updated?: string;
  };
  tnx: {
    yield: number | null;
    last_updated?: string;
  };
  dxy: {
    price: number | null;
    last_updated?: string;
  };
  health: MarketHealthScore;
}

export interface PriceResponse {
  symbol: string;
  price: number;
  beta: number | null;
  volatility: number | null;
  sector: string | null;
}

export interface PricesResponse {
  prices: Record<string, PriceResponse>;
  count: number;
}

export interface FearGreedReading {
  date: string;
  score: number;
  label: "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed";
  previous_score?: number;
  score_change?: number;
  signal_count: number;
}

export interface FearGreedComponent {
  date: string;
  vix_pct?: number;
  momentum_pct?: number;
  rsi_pct?: number;
  pcr_pct?: number;
  credit_pct?: number;
  window_days: number;
}

export interface FearGreedResponse {
  reading: FearGreedReading;
  components?: FearGreedComponent;
}

// Market Intelligence types (unified endpoint)
export interface EnrichedIndicator {
  value: number;
  change_pct: number | null;
  label: string;
  short_label: string;
  tooltip: string;
  signal: "Bullish" | "Neutral" | "Bearish";
  emoji: string;
  last_updated: string | null;
}

export interface SectorInfo {
  symbol: string;
  name: string;
  description: string;
  price: number | null;
  change_pct: number | null;
  signal: "Leading" | "Neutral" | "Lagging";
  last_updated: string | null;
}

export interface SectorRotationSummary {
  leading: SectorInfo[];
  neutral: SectorInfo[];
  lagging: SectorInfo[];
  leading_count: number;
  neutral_count: number;
  lagging_count: number;
}

export interface MarketHealthScoreSimple {
  overall_score: number;
  overall_label: string;
  last_updated: string;
  trend?: "up" | "down" | "flat" | null;
  trend_change?: number | null;
}

export interface FearGreedScore {
  score: number;
  label: "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed";
  score_change: number | null;
  signal_count: number;
  last_updated: string;
  is_stale: boolean;
  age_days: number;
  trend?: "up" | "down" | "flat" | null;
  trend_change?: number | null;
}

export interface SectorWeight {
  sector: string;
  weight_pct: number;
}

export interface OptionsActivityMetrics {
  near_term_pct: number;
  near_term_signal: "High" | "Normal" | "Low";
  concentration_pct: number;
  concentration_signal: "Focused" | "Balanced" | "Dispersed";
  top_sectors: SectorWeight[];
  last_updated: string;
}

export interface MarketIntelligenceResponse {
  narrative: string;
  market_health: MarketHealthScoreSimple;
  fear_greed: FearGreedScore;
  indicators: Record<string, EnrichedIndicator>;
  sector_rotation: SectorRotationSummary;
  options_activity: OptionsActivityMetrics | null;
  last_updated: string;
}

export interface MarketTrendsResponse {
  dates: string[];
  fear_greed_scores: number[];
  market_health_scores: number[];
}

/**
 * Get current market conditions (S&P 500, VIX, 10Y yield, USD index)
 */
export async function fetchMarketConditions(): Promise<MarketConditionsResponse> {
  return apiRequest<MarketConditionsResponse>("/api/market/conditions");
}

/**
 * Get unified market intelligence (narrative + dual scoring + sectors)
 */
export async function fetchMarketIntelligence(): Promise<MarketIntelligenceResponse> {
  return apiRequest<MarketIntelligenceResponse>("/api/market/intelligence");
}

/**
 * Get current prices for stock symbols
 */
export async function fetchPrices(symbols: string[]): Promise<PricesResponse> {
  const symbolsParam = symbols.join(",");

  return apiRequest<PricesResponse>(
    `/api/market/prices?symbols=${encodeURIComponent(symbolsParam)}`
  );
}

/**
 * Get Fear & Greed Index reading (latest or specific date)
 */
export async function fetchFearGreed(
  date?: string,
  includeComponents?: boolean
): Promise<FearGreedResponse> {
  const params = new URLSearchParams();
  if (date) params.append("date", date);
  if (includeComponents) params.append("include_components", "true");

  const queryString = params.toString();
  const url = queryString
    ? `/api/market/fear-greed?${queryString}`
    : "/api/market/fear-greed";

  return apiRequest<FearGreedResponse>(url);
}

/**
 * Get market trends for sparkline charts
 */
export async function fetchMarketTrends(days: number = 30): Promise<MarketTrendsResponse> {
  return apiRequest<MarketTrendsResponse>(`/api/market/trends?days=${days}`);
}

// ============================================================================
// Historical Data Types & Functions for Market Conditions Redesign
// ============================================================================

export interface FearGreedHistoryResponse {
  dates: string[];
  scores: number[];
  labels: string[];
}

export interface NewsSentimentHistoryResponse {
  dates: string[];
  scores: number[];  // -1 to +1
  positive_counts: number[];
  negative_counts: number[];
  article_counts: number[];
}

export interface IndicatorDataPoint {
  date: string;
  close: number;
  pct_change: number;
}

export interface IndicatorHistoryResponse {
  sp500: IndicatorDataPoint[];
  vix: IndicatorDataPoint[];
  tnx: IndicatorDataPoint[];
  dxy: IndicatorDataPoint[];
  period_start: string;
  period_end: string;
}

export interface SectorDataPoint {
  date: string;
  close: number;
  pct_change: number;
}

export interface SectorHistory {
  name: string;
  symbol: string;
  data: SectorDataPoint[];
  current_pct: number;
}

export interface SectorHistoryResponse {
  sectors: SectorHistory[];
  period_start: string;
  period_end: string;
}

/**
 * Get Fear & Greed historical data for trend charts
 */
export async function fetchFearGreedHistory(
  days: number = 365
): Promise<FearGreedHistoryResponse> {
  return apiRequest<FearGreedHistoryResponse>(
    `/api/market/fear-greed-history?days=${days}`
  );
}

/**
 * Get news sentiment historical data for trend charts
 * @param days - Number of days of history
 * @param granularity - 'daily' or 'hourly'
 */
export async function fetchNewsSentimentHistory(
  days: number = 30,
  granularity: "daily" | "hourly" = "daily"
): Promise<NewsSentimentHistoryResponse> {
  return apiRequest<NewsSentimentHistoryResponse>(
    `/api/market/news-sentiment-history?days=${days}&granularity=${granularity}`
  );
}

/**
 * Get key indicator historical data for trend charts
 */
export async function fetchIndicatorHistory(
  days: number = 365
): Promise<IndicatorHistoryResponse> {
  return apiRequest<IndicatorHistoryResponse>(
    `/api/market/indicator-history?days=${days}`
  );
}

/**
 * Get sector ETF historical data for performance charts
 */
export async function fetchSectorHistory(
  days: number = 365
): Promise<SectorHistoryResponse> {
  return apiRequest<SectorHistoryResponse>(
    `/api/market/sector-history?days=${days}`
  );
}

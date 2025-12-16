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
  lastUpdated?: string | null;
}

export interface SectorScore {
  symbol: string;
  name: string;
  price: number | null;
  changePct: number | null;
  signal: "Leading" | "Neutral" | "Lagging" | "Unknown";
  lastUpdated?: string | null;
}

export interface MarketHealthScore {
  overallScore: number;
  overallLabel: string;
  components: ComponentScore[];
  sectors: SectorScore[];
  lastUpdated: string;
}

export interface MarketConditionsResponse {
  sp500: {
    price: number | null;
    changePct: number | null;
    lastUpdated?: string;
  };
  vix: {
    price: number | null;
    level: number | null;
    lastUpdated?: string;
  };
  tnx: {
    yield: number | null;
    lastUpdated?: string;
  };
  dxy: {
    price: number | null;
    lastUpdated?: string;
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
  previousScore?: number;
  scoreChange?: number;
  signalCount: number;
}

export interface FearGreedComponent {
  date: string;
  vixPct?: number;
  momentumPct?: number;
  rsiPct?: number;
  pcrPct?: number;
  creditPct?: number;
  windowDays: number;
}

export interface FearGreedResponse {
  reading: FearGreedReading;
  components?: FearGreedComponent;
}

// Market Intelligence types (unified endpoint)
export interface PutCallContext {
  trend: "up" | "down" | "flat";
  trendPct: number;
  percentileRank: number;
}

export interface EnrichedIndicator {
  value: number;
  changePct: number | null;
  label: string;
  shortLabel: string;
  tooltip: string;
  signal: "Bullish" | "Neutral" | "Bearish";
  emoji: string;
  lastUpdated: string | null;
  context?: PutCallContext;  // Optional: present on putcall indicator
}

export interface SectorInfo {
  symbol: string;
  name: string;
  description: string;
  price: number | null;
  changePct: number | null;
  signal: "Leading" | "Neutral" | "Lagging";
  lastUpdated: string | null;
}

export interface SectorRotationSummary {
  leading: SectorInfo[];
  neutral: SectorInfo[];
  lagging: SectorInfo[];
  leadingCount: number;
  neutralCount: number;
  laggingCount: number;
}

export interface MarketHealthScoreSimple {
  overallScore: number;
  overallLabel: string;
  lastUpdated: string;
  trend?: "up" | "down" | "flat" | null;
  trendChange?: number | null;
}

export interface FearGreedScore {
  score: number;
  label: "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed";
  scoreChange: number | null;
  signalCount: number;
  lastUpdated: string;
  isStale: boolean;
  ageDays: number;
  trend?: "up" | "down" | "flat" | null;
  trendChange?: number | null;
}

export interface SectorWeight {
  sector: string;
  weightPct: number;
}

export interface OptionsActivityMetrics {
  nearTermPct: number;
  nearTermSignal: "High" | "Normal" | "Low";
  concentrationPct: number;
  concentrationSignal: "Focused" | "Balanced" | "Dispersed";
  topSectors: SectorWeight[];
  lastUpdated: string;
}

export interface MarketIntelligenceResponse {
  narrative: string;
  marketHealth: MarketHealthScoreSimple;
  fearGreed: FearGreedScore;
  indicators: Record<string, EnrichedIndicator>;
  sectorRotation: SectorRotationSummary;
  optionsActivity: OptionsActivityMetrics | null;
  lastUpdated: string;
}

export interface MarketTrendsResponse {
  dates: string[];
  fearGreedScores: number[];
  marketHealthScores: number[];
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
  putCallRatios: (number | null)[];
}

export interface NewsSentimentHistoryResponse {
  dates: string[];
  scores: number[];  // -1 to +1
  positiveCounts: number[];
  negativeCounts: number[];
  articleCounts: number[];
}

export interface IndicatorDataPoint {
  date: string;
  close: number;
  pctChange: number;
}

export interface IndicatorHistoryResponse {
  sp500: IndicatorDataPoint[];
  vix: IndicatorDataPoint[];
  tnx: IndicatorDataPoint[];
  dxy: IndicatorDataPoint[];
  periodStart: string;
  periodEnd: string;
}

export interface SectorDataPoint {
  date: string;
  close: number;
  pctChange: number;
}

export interface SectorHistory {
  name: string;
  symbol: string;
  data: SectorDataPoint[];
  currentPct: number;
}

export interface SectorHistoryResponse {
  sectors: SectorHistory[];
  periodStart: string;
  periodEnd: string;
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

// ============================================================================
// Market Movers Types & Functions
// ============================================================================

export interface MarketMoverItem {
  symbol: string;
  name: string | null;
  price: number;
  changePct: number;
  volume: number | null;
  marketCap: number | null;
  avgVolume: number | null;
  rvol: number | null;
  sector: string | null;
}

export interface MarketMoversResponse {
  gainers: MarketMoverItem[];
  losers: MarketMoverItem[];
  mostActive: MarketMoverItem[];
  topRvol: MarketMoverItem[];
  source: string;
  lastUpdated: string | null;
}

/**
 * Get top market movers (gainers and losers)
 */
export async function fetchMarketMovers(
  count: number = 10
): Promise<MarketMoversResponse> {
  return apiRequest<MarketMoversResponse>(
    `/api/market/movers?count=${count}`
  );
}

// ============================================================================
// Market Status Types & Functions
// ============================================================================

export interface MarketStatusResponse {
  status: "open" | "closed" | "pre_market" | "after_hours";
  isOpen: boolean;
  lastTradingDay: string;
  nextTradingDay: string;
  currentTimeEt: string;
  expectedDataDate: string;
  isHoliday: boolean;
  holidayName: string | null;
  isEarlyClose: boolean;
  earlyCloseName: string | null;
}

/**
 * Get current market status including expected data date for staleness detection
 */
export async function fetchMarketStatus(): Promise<MarketStatusResponse> {
  return apiRequest<MarketStatusResponse>("/api/market/status");
}

// =============================================================================
// Market Events (FOMC, CPI, NFP, etc.)
// =============================================================================

export interface MarketEvent {
  id: number;
  date: string;
  time: string | null;
  type: string;
  title: string;
  label: string;
  color: string;
  impactScore: number | null;
  actualValue: number | null;
  expectedValue: number | null;
  surprisePct: number | null;
}

export interface MarketEventsChartResponse {
  events: MarketEvent[];
  total: number;
  startDate: string;
  endDate: string;
}

export interface MarketEventType {
  eventType: string;
  label: string;
  shortLabel: string;
  color: string;
  frequency: string;
  impact: string;
}

export interface MarketEventTypesResponse {
  types: MarketEventType[];
}

/**
 * Fetch market events formatted for chart overlays
 */
export async function fetchMarketEventsForChart(
  days: number = 365
): Promise<MarketEventsChartResponse> {
  return apiRequest<MarketEventsChartResponse>(
    `/api/market/events/chart?days=${days}`
  );
}

/**
 * Fetch market event type metadata
 */
export async function fetchMarketEventTypes(): Promise<MarketEventTypesResponse> {
  return apiRequest<MarketEventTypesResponse>("/api/market/events/types");
}

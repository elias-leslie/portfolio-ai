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
}

export interface SectorScore {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  signal: "Leading" | "Neutral" | "Lagging" | "Unknown";
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
  };
  vix: {
    price: number | null;
    level: number | null;
  };
  tnx: {
    yield: number | null;
  };
  dxy: {
    price: number | null;
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

/**
 * Get current market conditions (S&P 500, VIX, 10Y yield, USD index)
 */
export async function fetchMarketConditions(): Promise<MarketConditionsResponse> {
  return apiRequest<MarketConditionsResponse>("/api/market/conditions");
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

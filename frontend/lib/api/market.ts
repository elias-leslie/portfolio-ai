/**
 * Market data API client functions
 */

import { apiRequest } from "./client";

// Types matching backend Pydantic models
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

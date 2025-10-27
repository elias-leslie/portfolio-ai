/**
 * Market data API client functions
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  const response = await fetch(`${API_BASE_URL}/api/market/conditions`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(
      `Failed to fetch market conditions: ${response.statusText}`
    );
  }

  return response.json();
}

/**
 * Get current prices for stock symbols
 */
export async function fetchPrices(symbols: string[]): Promise<PricesResponse> {
  const symbolsParam = symbols.join(",");

  const response = await fetch(
    `${API_BASE_URL}/api/market/prices?symbols=${encodeURIComponent(symbolsParam)}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch prices: ${response.statusText}`);
  }

  return response.json();
}

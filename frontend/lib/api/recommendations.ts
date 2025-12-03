/**
 * Recommendations API client functions
 */

import { apiRequest } from "./client";

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface TradeRecommendation {
  symbol: string;
  strategy_id: string;
  strategy_name: string;
  strategy_type: string;
  signal_strength: number;
  signal_type: "BUY" | "SELL" | "HOLD";
  signal_reasons: string[];
  entry_price: number;  // Price when signal was generated
  current_price: number;  // Real-time current price
  price_change_pct: number;  // % change since signal
  signal_status: "valid" | "better_entry" | "caution" | "invalidated";
  stop_loss: number;
  target_price: number;
  position_size_dollars: number;
  position_size_shares: number;
  risk_reward_ratio: number;
  expected_sharpe: number | null;
  signal_date: string;
  generated_at: string | null;
}

export interface RecommendationsSummary {
  buy_signals: number;
  sell_signals: number;
  hold_signals: number;
  total_position_size: number;
  avg_signal_strength: number;
  portfolio_size: number;
  position_pct: number;
}

export interface RecommendationsResponse {
  recommendations: TradeRecommendation[];
  total: number;
  summary: RecommendationsSummary;
}

export interface RecommendedSymbol {
  symbol: string;
  strength: number;
}

export interface RecommendedSymbolsResponse {
  symbols: RecommendedSymbol[];
  count: number;
}

export interface PaperTradeResponse {
  status: string;
  trade: {
    symbol: string;
    shares: number;
    entry_price: number;
    total_cost: number;
    strategy_name: string;
  };
  message: string;
}

export interface TrackPortfolioResponse {
  status: string;
  position: {
    id: string;
    symbol: string;
    shares: number;
    cost_basis: number;
    account_name: string;
    strategy_name: string;
  };
  message: string;
}

// ============================================================================
// API Functions
// ============================================================================

export async function getRecommendations(params?: {
  min_strength?: number;
  limit?: number;
  signal_type?: "BUY" | "SELL" | "all";
  portfolio_size?: number;
  position_pct?: number;
}): Promise<RecommendationsResponse> {
  const searchParams = new URLSearchParams();
  if (params?.min_strength !== undefined) searchParams.set("min_strength", params.min_strength.toString());
  if (params?.limit) searchParams.set("limit", params.limit.toString());
  if (params?.signal_type) searchParams.set("signal_type", params.signal_type);
  if (params?.portfolio_size) searchParams.set("portfolio_size", params.portfolio_size.toString());
  if (params?.position_pct) searchParams.set("position_pct", params.position_pct.toString());

  const query = searchParams.toString();
  return apiRequest<RecommendationsResponse>(`/api/recommendations/${query ? `?${query}` : ""}`);
}

export async function getRecommendedSymbols(
  minStrength = 5
): Promise<RecommendedSymbolsResponse> {
  return apiRequest<RecommendedSymbolsResponse>(
    `/api/recommendations/symbols?min_strength=${minStrength}`
  );
}

export async function paperTradeRecommendation(
  symbol: string,
  strategyId: string
): Promise<PaperTradeResponse> {
  const params = new URLSearchParams();
  params.set("strategy_id", strategyId);

  return apiRequest<PaperTradeResponse>(
    `/api/recommendations/paper-trade/${symbol}?${params.toString()}`,
    { method: "POST" }
  );
}

export async function trackInPortfolio(
  symbol: string,
  strategyId: string,
  accountId: string,
  shares: number
): Promise<TrackPortfolioResponse> {
  const params = new URLSearchParams();
  params.set("strategy_id", strategyId);
  params.set("account_id", accountId);
  params.set("shares", shares.toString());

  return apiRequest<TrackPortfolioResponse>(
    `/api/recommendations/track/${symbol}?${params.toString()}`,
    { method: "POST" }
  );
}

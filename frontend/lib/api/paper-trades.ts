/**
 * Paper Trading API client functions
 */

import { apiRequest } from "./client";

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface PaperTrade {
  idea_id: string;
  agent_run_id: string;
  ticker: string;
  idea_type: "buy" | "sell";
  entry_price?: number;
  entry_date?: string;
  target_price?: number;
  stop_loss_price?: number;
  current_price?: number;
  current_return_pct?: number;
  status: string;
  exit_price?: number;
  exit_date?: string;
  exit_reason?: string;
  realized_return_pct?: number;
  holding_days?: number;
  max_favorable_pct?: number;
  max_adverse_pct?: number;
  // AI reasoning fields
  thesis?: string;
  confidence_score?: number;
  risk_level?: string;
  // Agent approval details
  workflow_id?: string;
  strategy_agent_approved?: boolean;
  risk_agent_approved?: boolean;
  backtest_sharpe?: number;
  backtest_win_rate?: number;
  backtest_max_drawdown?: number;
}

export interface PaperTradesListResponse {
  trades: PaperTrade[];
  total_count: number;
}

export interface PaperTradeSummary {
  total_open: number;
  total_closed: number;
  win_rate: number;
  avg_return_pct: number;
  total_pnl_pct: number;
  best_trade_pct?: number;
  worst_trade_pct?: number;
}

export interface CloseTradeRequest {
  exit_price?: number;
  exit_reason?: string;
}

export interface CloseTradeResponse {
  status: string;
  trade_id: string;
  ticker: string;
  exit_price: number;
  exit_date: string;
  realized_return_pct: number;
  message: string;
}

export interface CreateTradeRequest {
  ticker: string;
  action: "buy" | "sell";
  thesis: string;
  target_price?: number;
  stop_loss_pct?: number;
}

export interface CreateTradeResponse {
  status: string;
  trade_id?: string;
  ticker?: string;
  action?: string;
  shares?: number;
  entry_price?: number;
  entry_amount?: number;
  target_price?: number;
  stop_loss_price?: number;
  cash_remaining?: number;
  message: string;
  error?: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create a manual paper trade
 */
export async function createPaperTrade(
  request: CreateTradeRequest
): Promise<CreateTradeResponse> {
  return apiRequest<CreateTradeResponse>("/api/paper-trading/trades", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

/**
 * Fetch all paper trades with optional status filter
 */
export async function fetchPaperTrades(params?: {
  status?: "open" | "closed" | "all";
  limit?: number;
  offset?: number;
}): Promise<PaperTradesListResponse> {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append("status", params.status);
  if (params?.limit) queryParams.append("limit", String(params.limit));
  if (params?.offset) queryParams.append("offset", String(params.offset));

  const url = `/api/paper-trades${queryParams.toString() ? `?${queryParams}` : ""}`;
  return apiRequest<PaperTradesListResponse>(url);
}

/**
 * Fetch paper trading summary statistics
 */
export async function fetchPaperTradeSummary(): Promise<PaperTradeSummary> {
  return apiRequest<PaperTradeSummary>("/api/paper-trades/summary");
}

/**
 * Fetch a single paper trade by ID
 */
export async function fetchPaperTrade(tradeId: string): Promise<PaperTrade> {
  return apiRequest<PaperTrade>(`/api/paper-trades/${tradeId}`);
}

/**
 * Close a paper trade manually
 */
export async function closePaperTrade(
  tradeId: string,
  request: CloseTradeRequest
): Promise<CloseTradeResponse> {
  return apiRequest<CloseTradeResponse>(`/api/paper-trades/${tradeId}/close`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

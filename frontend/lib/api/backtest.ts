/**
 * Backtesting API client functions
 */

import { apiRequest } from "./client";

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface BacktestRun {
  id: string;
  symbol: string;
  strategy_name: string;
  start_date: string;
  end_date: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  initial_capital: string | number;
  final_equity: string | number | null;
  total_return_pct: string | number | null;
  sharpe_ratio: string | number | null;
  max_drawdown_pct: string | number | null;
  win_rate: string | number | null;
  num_trades: number | null;
  profit_factor: string | number | null;
  error_message?: string | null;
  completed_at?: string | null;
}

export interface BacktestTrade {
  id: string;
  run_id: string;
  symbol: string;
  entry_date: string;
  entry_price: string | number;
  exit_date: string | null;
  exit_price: string | number | null;
  shares: number;
  pnl: string | number | null;
  pnl_pct: string | number | null;
  exit_reason: "target" | "stop" | "signal" | "time" | "eod" | null;
  max_favorable_pct: string | number;
  max_adverse_pct: string | number;
  created_at: string;
}

export interface BacktestEquity {
  id: string;
  run_id: string;
  date: string;
  equity: string | number;
  cash: string | number;
  position_value: string | number;
  drawdown_pct: string | number;
  cumulative_return_pct: string | number;
  created_at: string;
}

export interface BacktestResult {
  run: BacktestRun;
  trades: BacktestTrade[];
  equity_curve: BacktestEquity[];
  avg_win?: string | number | null;
  avg_loss?: string | number | null;
  win_loss_ratio?: string | number | null;
  num_wins?: number;
  num_losses?: number;
  total_days?: number;
}

export interface StrategyParameters {
  stop_loss_atr_multiplier?: number;
  max_holding_days?: number;
  target_profit_pct?: number;
  min_confirmations?: number;
}

export interface StartBacktestRequest {
  symbol: string;
  strategy: string;
  start_date: string;
  end_date: string;
  parameters?: StrategyParameters;
}

export interface StartBacktestResponse {
  run_id: string;
  symbol: string;
  strategy: string;
  status: "pending" | "running";
  message: string;
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch all backtest runs
 */
export async function fetchBacktestRuns(): Promise<BacktestRun[]> {
  return apiRequest<BacktestRun[]>("/api/backtest/runs");
}

/**
 * Fetch a single backtest run details
 */
export async function fetchBacktestRun(runId: string): Promise<BacktestResult> {
  return apiRequest<BacktestResult>(`/api/backtest/runs/${runId}`);
}

/**
 * Fetch equity curve data for a backtest run
 */
export async function fetchBacktestEquity(runId: string): Promise<BacktestEquity[]> {
  return apiRequest<BacktestEquity[]>(`/api/backtest/runs/${runId}/equity`);
}

/**
 * Start a new backtest
 */
export async function startBacktest(
  request: StartBacktestRequest
): Promise<StartBacktestResponse> {
  return apiRequest<StartBacktestResponse>("/api/backtest/runs", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

/**
 * Delete a backtest run
 */
export async function deleteBacktestRun(runId: string): Promise<{ message: string }> {
  return apiRequest<{ message: string }>(`/api/backtest/runs/${runId}`, {
    method: "DELETE",
  });
}

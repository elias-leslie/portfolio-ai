/**
 * Strategies API client functions
 */

import { apiRequest } from "./client";

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface StrategyListItem {
  id: string;
  name: string;
  symbol: string;
  strategy_type: string;
  status: "testing" | "active" | "archived";
  version: number;
  expected_sharpe: number | null;
  live_sharpe_ratio: number | null;
  live_win_rate: number | null;
  trades_count: number;
  created_at: string;
  activation_date: string | null;
}

export interface StrategyDetail extends StrategyListItem {
  parameters: Record<string, unknown>;
  research_summary: ResearchSummary;
  generation_reasoning: string;
  backtest_metrics: BacktestMetric[];
  expected_win_rate: number | null;
  expected_max_drawdown: number | null;
  live_trades_count: number;
  archive_date: string | null;
  archive_reason: string | null;
  performance_history: PerformanceHistoryEntry[];
}

export interface ResearchSummary {
  symbol: string;
  as_of_date: string;
  news_sentiment_trend: string;
  news_sentiment_score: number;
  company_health: string;
  fundamental_score: number;
  valuation_tier: string;
  trend_strength: string;
  market_regime: string;
  fear_greed_score: number;
  sector: string;
  sector_momentum: string;
  overall_confidence: number;
}

export interface BacktestMetric {
  window_start: string;
  window_end: string;
  sharpe: number;
  win_rate: number;
  max_drawdown: number;
  total_return: number;
}

export interface PerformanceHistoryEntry {
  date: string;
  trades_30d: number;
  win_rate_30d: number | null;
  sharpe_ratio_30d: number | null;
  max_drawdown_30d: number | null;
  status: string;
}

export interface StrategiesListResponse {
  strategies: StrategyListItem[];
  total: number;
}

export interface GenerateStrategyRequest {
  symbol: string;
  force_regenerate?: boolean;
}

export interface GenerateBatchRequest {
  symbols?: string[];
  top_n?: number;
  force_regenerate?: boolean;
}

export interface GenerateStrategyResponse {
  workflow_id?: string;
  status: string;
  strategy_id?: string;
  commit_sha?: string;
  message?: string;
  error_message?: string;
}

export interface GenerateBatchResponse {
  status: string;
  symbols_processed?: number;
  strategies_generated?: number;
  symbols_evaluated?: number;
  results?: Array<{
    symbol: string;
    status: string;
    strategy_id: string | null;
    message: string | null;
  }>;
  details?: string[];
}

export interface UpdateStrategyStatusRequest {
  status: "active" | "archived";
  archive_reason?: string;
}

export interface StrategyPerformance {
  expected: {
    sharpe: number;
    win_rate: number | null;
    max_drawdown: number | null;
  };
  actual_30d: {
    sharpe: number;
    win_rate: number | null;
    trades_count: number;
  };
  performance_ratio: number;
  status: "no_live_data" | "exceeding_expectations" | "meeting_expectations" | "underperforming";
}

// ============================================================================
// API Functions
// ============================================================================

export async function getStrategies(params?: {
  symbol?: string;
  status?: "testing" | "active" | "archived";
  strategy_type?: string;
  limit?: number;
}): Promise<StrategiesListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.symbol) searchParams.set("symbol", params.symbol);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.strategy_type) searchParams.set("strategy_type", params.strategy_type);
  if (params?.limit) searchParams.set("limit", params.limit.toString());

  const query = searchParams.toString();
  return apiRequest<StrategiesListResponse>(`/api/strategies/${query ? `?${query}` : ""}`);
}

export async function getStrategy(strategyId: string): Promise<StrategyDetail> {
  return apiRequest<StrategyDetail>(`/api/strategies/${strategyId}`);
}

export async function generateStrategy(
  request: GenerateStrategyRequest
): Promise<GenerateStrategyResponse> {
  return apiRequest<GenerateStrategyResponse>("/api/strategies/generate", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function generateStrategiesBatch(
  request: GenerateBatchRequest
): Promise<GenerateBatchResponse> {
  return apiRequest<GenerateBatchResponse>("/api/strategies/generate-batch", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function updateStrategyStatus(
  strategyId: string,
  request: UpdateStrategyStatusRequest
): Promise<{ strategy: StrategyListItem; message: string }> {
  return apiRequest<{ strategy: StrategyListItem; message: string }>(
    `/api/strategies/${strategyId}`,
    {
      method: "PATCH",
      body: JSON.stringify(request),
    }
  );
}

export async function getStrategyPerformance(
  strategyId: string
): Promise<StrategyPerformance> {
  return apiRequest<StrategyPerformance>(`/api/strategies/${strategyId}/performance`);
}

// ============================================================================
// Strategy Seeds API (FEAT-218)
// ============================================================================

export interface StrategySeed {
  id: string;
  symbol: string;
  thesis: string;
  confidence: number;
  status: "pending" | "processing" | "converted" | "rejected";
  strategy_id: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface StrategySeedsListResponse {
  seeds: StrategySeed[];
  total: number;
}

export interface StrategyEvolution {
  strategy_id: string;
  name: string;
  symbol: string;
  status: string;
  seed: {
    id: string;
    thesis: string;
    confidence: number;
    created_at: string;
  } | null;
  backtests: Array<{
    id: string;
    start_date: string | null;
    end_date: string | null;
    sharpe_ratio: number | null;
    total_return_pct: number | null;
    max_drawdown_pct: number | null;
    win_rate: number | null;
    num_trades: number;
    status: string;
    created_at: string | null;
  }>;
  signals: Array<{
    id: string;
    action: string;
    strength: number | null;
    confidence_score: number | null;
    entry_price: number | null;
    target_price: number | null;
    created_at: string | null;
  }>;
  trades: Array<{
    id: string;
    symbol: string;
    entry_price: number | null;
    exit_price: number | null;
    return_pct: number | null;
    status: string;
    created_at: string | null;
  }>;
  performance: {
    expected_sharpe: number | null;
    live_sharpe: number | null;
    live_win_rate: number | null;
    total_trades: number;
  };
}

export async function getStrategySeeds(params?: {
  status?: string;
  symbol?: string;
  limit?: number;
  offset?: number;
}): Promise<StrategySeedsListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set("status", params.status);
  if (params?.symbol) searchParams.set("symbol", params.symbol);
  if (params?.limit) searchParams.set("limit", params.limit.toString());
  if (params?.offset) searchParams.set("offset", params.offset.toString());

  const query = searchParams.toString();
  return apiRequest<StrategySeedsListResponse>(
    `/api/strategy-seeds/${query ? `?${query}` : ""}`
  );
}

export async function getStrategySeed(seedId: string): Promise<StrategySeed> {
  return apiRequest<StrategySeed>(`/api/strategy-seeds/${seedId}`);
}

export async function getStrategyEvolution(strategyId: string): Promise<StrategyEvolution> {
  return apiRequest<StrategyEvolution>(`/api/strategies/${strategyId}/evolution`);
}

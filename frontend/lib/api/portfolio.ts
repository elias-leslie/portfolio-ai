/**
 * Portfolio API client functions
 */

import { apiRequest } from "./client";

// Types matching backend Pydantic models
export interface Account {
  id: string;
  name: string;
  account_type: string;
  created_at: string;
  updated_at: string;
}

export interface Position {
  id: string;
  account_id: string;
  symbol: string;
  shares: number;
  cost_basis: number;
  position_type: string;
  created_at: string;
  updated_at: string;
}

export interface PositionWithValue extends Position {
  current_price: number;
  current_value: number;
  gain: number;
  gain_pct: number;
}

export interface PortfolioResponse {
  positions: PositionWithValue[];
  total_value: number;
  total_cost_basis: number;
  total_gain: number;
  total_gain_pct: number;
}

export interface PositionPerformance {
  symbol: string;
  gain_pct: number;
  gain_amount: number;
  current_value: number;
  weight_pct: number;
}

export interface RiskProfile {
  level: string;
  score: number;
  factors: Record<string, string>;
}

export interface DiversificationScore {
  score: number;
  level: string;
  num_holdings: number;
  num_sectors: number;
}

export interface PortfolioAnalytics {
  portfolio_value: {
    total_value: number;
    total_cost_basis: number;
    total_gain: number;
    total_gain_pct: number;
  };
  portfolio_beta: number;
  portfolio_volatility: number;
  sharpe_ratio: number | null;
  concentration: {
    top_holding_pct: number;
    top_3_pct: number;
    top_10_pct: number;
    herfindahl_index: number;
  };
  sector_exposure: Record<string, number>;
  risk_profile: RiskProfile | null;
  diversification_score: DiversificationScore | null;
  top_performers: PositionPerformance[];
  bottom_performers: PositionPerformance[];
  num_positions: number;
  num_symbols: number;
}

export interface CreateAccountRequest {
  name: string;
  account_type: string;
}

export interface AddPositionRequest {
  account_id: string;
  symbol: string;
  shares: number;
  cost_basis: number;
  position_type: string;
}

/**
 * Fetch all portfolio positions with current values
 */
export async function fetchPortfolio(): Promise<PortfolioResponse> {
  return apiRequest<PortfolioResponse>("/api/portfolio/");
}

/**
 * Fetch all accounts
 */
export async function fetchAccounts(): Promise<Account[]> {
  return apiRequest<Account[]>("/api/portfolio/accounts");
}

/**
 * Create a new account
 */
export async function createAccount(
  data: CreateAccountRequest
): Promise<Account> {
  return apiRequest<Account>("/api/portfolio/account", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Delete an account by ID
 */
export async function deleteAccount(accountId: string): Promise<void> {
  await apiRequest<void>(`/api/portfolio/account/${accountId}`, {
    method: "DELETE",
  });
}

/**
 * Add or update a position
 */
export async function addPosition(
  data: AddPositionRequest
): Promise<Position> {
  return apiRequest<Position>("/api/portfolio/position", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing position
 */
export async function updatePosition(
  positionId: string,
  data: AddPositionRequest
): Promise<Position> {
  return apiRequest<Position>(`/api/portfolio/position/${positionId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

/**
 * Delete a position by ID
 */
export async function deletePosition(positionId: string): Promise<void> {
  await apiRequest<void>(`/api/portfolio/position/${positionId}`, {
    method: "DELETE",
  });
}

/**
 * Fetch portfolio analytics (beta, volatility, concentration, sector exposure)
 */
export async function fetchAnalytics(): Promise<PortfolioAnalytics> {
  return apiRequest<PortfolioAnalytics>("/api/portfolio/analytics");
}

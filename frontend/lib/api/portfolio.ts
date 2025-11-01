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

export interface PortfolioAnalytics {
  total_value: number;
  total_cost_basis: number;
  total_gain: number;
  total_gain_pct: number;
  portfolio_beta: number;
  portfolio_volatility: number;
  concentration: {
    top_holding_pct: number;
    top_3_pct: number;
    top_10_pct: number;
    herfindahl_index: number;
  };
  sector_exposure: Record<string, number>;
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
